import { SimliClient, LogLevel } from "simli-client";

const LOG_PREFIX = "[DoctorAvatar]";

// The Simli SDK retries start() internally (~2s apart), so bound how long a
// (re)connect may take instead of leaving the avatar on "connecting" forever.
const CONNECT_TIMEOUT_MS = 25000;
// After audio is sent: how long to wait for Simli to report "speaking", and
// how much slack beyond the audio's own length to wait for "silent", before
// giving up and returning to idle so Live Voice can never stay stuck.
const SPEAK_START_TIMEOUT_MS = 10000;
const SPEAK_END_MARGIN_MS = 8000;
const PCM16_16KHZ_BYTES_PER_MS = 32;

export class DoctorAvatar {
  constructor({ videoEl, audioEl, panelEl, stateEl }) {
    this.videoEl = videoEl;
    this.audioEl = audioEl;
    this.panelEl = panelEl;
    this.stateEl = stateEl;
    this.client = null;
    this.state = "connecting";
    this._audioUnlocked = false;
    // True only while the current Simli session is usable. Simli ends a
    // session on its own after its idle / max-length limits (see
    // app/avatar_simli.py), so the page must be able to tell and reconnect.
    this._live = false;
    this._connecting = null;
    this._watchdog = null;
    this._speakMs = 0;
    this._setState("connecting");
    this._setupAudioUnlock();
  }

  // Chrome (and other browsers) block <audio>/<video> playback that has sound
  // until the page has received a real user gesture. Simli's video track has
  // no sound (audio arrives on a separate <audio> element), so it autoplays
  // fine — but that separate <audio> element's first play() attempt, fired
  // automatically by the SDK the moment the remote track arrives, happens
  // before any click and is rejected by the browser. This does not create or
  // resume any AudioContext, and does not call play() itself before a
  // gesture — it only retries the SAME element's play() once a gesture has
  // actually happened, which is what actually unlocks it.
  _setupAudioUnlock() {
    const unlock = () => {
      if (this._audioUnlocked) return;
      this._audioUnlocked = true;
      console.log(LOG_PREFIX, "user gesture detected — retrying audio playback");
      const playPromise = this.audioEl.play();
      if (playPromise && typeof playPromise.then === "function") {
        playPromise
          .then(() => console.log(LOG_PREFIX, "audio playback unlocked successfully"))
          .catch((error) =>
            console.warn(LOG_PREFIX, "audio playback still blocked after gesture (will retry on next speak):", error),
          );
      }
      document.removeEventListener("click", unlock);
      document.removeEventListener("keydown", unlock);
      document.removeEventListener("touchstart", unlock);
    };
    document.addEventListener("click", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
    document.addEventListener("touchstart", unlock, { once: true });
  }

  // Resolves true once a session is live, false if it could not be
  // established (state is then "error"). Never throws. Concurrent callers
  // share one in-flight attempt.
  connect() {
    if (!this._connecting) {
      this._connecting = this._connect().finally(() => {
        this._connecting = null;
      });
    }
    return this._connecting;
  }

  // Cheap no-op while a live session exists; reconnects if it has ended.
  ensureConnected() {
    return this._live ? Promise.resolve(true) : this.connect();
  }

  async _connect() {
    console.log(LOG_PREFIX, "connect() starting");
    this._clearWatchdog();
    this._live = false;
    await this._releaseClient();
    this._setState("connecting");
    let client = null;
    let timer = null;
    try {
      console.log(LOG_PREFIX, "requesting session token from /avatar/session");
      const response = await fetch("/avatar/session", { method: "POST" });
      console.log(LOG_PREFIX, "/avatar/session HTTP status:", response.status);
      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error("Failed to create avatar session: " + errorBody);
      }
      const { session_token } = await response.json();
      console.log(LOG_PREFIX, "got session token, length:", session_token.length);

      client = new SimliClient(
        session_token,
        this.videoEl,
        this.audioEl,
        null,
        LogLevel.DEBUG,
        "livekit",
      );
      this.client = client;
      console.log(LOG_PREFIX, "SimliClient constructed");

      // Events from a client we have since replaced must not touch state.
      const current = (handler) => (...args) => {
        if (this.client === client) handler(...args);
      };

      client.on("start", current(() => {
        console.log(LOG_PREFIX, "event: start (first video frame received)");
        this._live = true;
        this._setState("idle");
      }));
      client.on("stop", current(() => {
        console.log(LOG_PREFIX, "event: stop — session ended, will reconnect on next use");
        this._live = false;
        this._clearWatchdog();
        if (this.state === "speaking" || this.state === "thinking") this._setState("idle");
      }));
      client.on("speaking", current(() => {
        console.log(LOG_PREFIX, "event: speaking");
        this._setState("speaking");
        this._armWatchdog(this._speakMs + SPEAK_END_MARGIN_MS);
      }));
      client.on("silent", current(() => {
        console.log(LOG_PREFIX, "event: silent");
        this._clearWatchdog();
        this._setState("idle");
      }));
      client.on("error", current((detail) => {
        console.error(LOG_PREFIX, "event: error —", detail);
        this._live = false;
        this._clearWatchdog();
        this._setState("error");
      }));
      client.on("startup_error", current((detail) => {
        console.error(LOG_PREFIX, "event: startup_error —", detail);
        this._live = false;
        this._setState("error");
      }));
      client.on("ack", () => {
        console.log(LOG_PREFIX, "event: ack");
      });
      client.on("connection_info", (info) => {
        console.log(LOG_PREFIX, "event: connection_info —", info);
      });
      client.on("video_info", (info) => {
        console.log(LOG_PREFIX, "event: video_info —", info);
      });
      client.on("unknown", (message) => {
        console.log(LOG_PREFIX, "event: unknown —", message);
      });

      console.log(LOG_PREFIX, "calling client.start() — waiting for first video frame");
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("timed out waiting for the avatar to connect")),
          CONNECT_TIMEOUT_MS,
        );
      });
      await Promise.race([client.start(), timeout]);
      console.log(LOG_PREFIX, "client.start() resolved — connected");
      this._live = true;
      this._setState("idle");
      return true;
    } catch (error) {
      console.error(LOG_PREFIX, "connect() failed:", error);
      this._live = false;
      if (client && this.client === client) {
        this.client = null;
        this._stopClient(client);
      }
      this._setState("error");
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  think() {
    console.log(LOG_PREFIX, "think() — state -> thinking");
    this._setState("thinking");
  }

  // Resolves true once the reply audio has been handed to Simli, false if it
  // could not be played (TTS failure or no avatar session). Never throws, and
  // always leaves the state at "thinking"/"speaking" (in flight) or back at
  // "idle" / "error" — never stuck.
  async speak(text, voiceId) {
    console.log(LOG_PREFIX, "speak() called, live:", this._live, "text length:", text.length);
    this._setState("thinking");
    try {
      // Fetch the speech while (re)connecting so a dead session only costs
      // the reconnect time, not reconnect + TTS in sequence.
      const [live, audio] = await Promise.all([
        this.ensureConnected(),
        this._fetchSpeech(text, voiceId),
      ]);
      if (!live) throw new Error("avatar session unavailable");
      // A reconnect passes through "idle"; hold "thinking" so Live Voice
      // does not start listening while the reply is about to play.
      this._setState("thinking");
      this._speakMs = audio.byteLength / PCM16_16KHZ_BYTES_PER_MS;
      this.client.sendAudioData(audio);
      this._armWatchdog(SPEAK_START_TIMEOUT_MS);
      console.log(LOG_PREFIX, "audio data sent to Simli client");
      return true;
    } catch (error) {
      console.error(LOG_PREFIX, "speak() failed:", error);
      this._clearWatchdog();
      // Simli fine but TTS failed -> idle (text reply still shown, voice loop
      // can continue). No usable session -> error.
      this._setState(this._live ? "idle" : "error");
      return false;
    }
  }

  async _fetchSpeech(text, voiceId) {
    console.log(LOG_PREFIX, "requesting TTS audio from /tts, voiceId:", voiceId || "(default)");
    const response = await fetch("/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(voiceId ? { text, voice_id: voiceId } : { text }),
    });
    console.log(LOG_PREFIX, "/tts HTTP status:", response.status);
    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error("TTS request failed: " + errorBody);
    }
    const buffer = await response.arrayBuffer();
    console.log(LOG_PREFIX, "got audio bytes:", buffer.byteLength, "(", (buffer.byteLength / 32000).toFixed(2), "sec of PCM16 16kHz)");
    return new Uint8Array(buffer);
  }

  // If Simli never confirms "speaking" / "silent" (e.g. the session died
  // without an event), stop waiting: go idle and reconnect on next use.
  _armWatchdog(ms) {
    this._clearWatchdog();
    this._watchdog = setTimeout(() => {
      this._watchdog = null;
      console.warn(LOG_PREFIX, "watchdog: no response from Simli — returning to idle, will reconnect on next use");
      this._live = false;
      if (this.state === "speaking" || this.state === "thinking") this._setState("idle");
    }, ms);
  }

  _clearWatchdog() {
    if (this._watchdog) {
      clearTimeout(this._watchdog);
      this._watchdog = null;
    }
  }

  // Wait (bounded) for the previous client to release the shared video/audio
  // elements before a new one attaches to them.
  async _releaseClient() {
    const previous = this.client;
    this.client = null;
    if (!previous) return;
    await Promise.race([
      this._stopClient(previous),
      new Promise((resolve) => setTimeout(resolve, 3000)),
    ]);
  }

  async _stopClient(client) {
    try {
      await client.stop();
    } catch (error) {
      console.warn(LOG_PREFIX, "stopping previous client failed (ignored):", error);
    }
  }

  _setState(state) {
    console.log(LOG_PREFIX, "state ->", state);
    this.state = state;
    if (this.stateEl) {
      this.stateEl.textContent = state;
    }
    if (this.panelEl) {
      this.panelEl.dataset.state = state;
    }
  }
}
