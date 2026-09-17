import { SimliClient, LogLevel } from "simli-client";

const LOG_PREFIX = "[DoctorAvatar]";

export class DoctorAvatar {
  constructor({ videoEl, audioEl, panelEl, stateEl }) {
    this.videoEl = videoEl;
    this.audioEl = audioEl;
    this.panelEl = panelEl;
    this.stateEl = stateEl;
    this.client = null;
    this.state = "connecting";
    this._setState("connecting");
  }

  async connect() {
    console.log(LOG_PREFIX, "connect() starting");
    this._setState("connecting");
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

      this.client = new SimliClient(
        session_token,
        this.videoEl,
        this.audioEl,
        null,
        LogLevel.DEBUG,
        "livekit",
      );
      console.log(LOG_PREFIX, "SimliClient constructed");

      this.client.on("start", () => {
        console.log(LOG_PREFIX, "event: start (first video frame received)");
        this._setState("idle");
      });
      this.client.on("stop", () => {
        console.log(LOG_PREFIX, "event: stop");
      });
      this.client.on("speaking", () => {
        console.log(LOG_PREFIX, "event: speaking");
        this._setState("speaking");
      });
      this.client.on("silent", () => {
        console.log(LOG_PREFIX, "event: silent");
        this._setState("idle");
      });
      this.client.on("error", (detail) => {
        console.error(LOG_PREFIX, "event: error —", detail);
        this._setState("error");
      });
      this.client.on("startup_error", (detail) => {
        console.error(LOG_PREFIX, "event: startup_error —", detail);
        this._setState("error");
      });
      this.client.on("ack", () => {
        console.log(LOG_PREFIX, "event: ack");
      });
      this.client.on("connection_info", (info) => {
        console.log(LOG_PREFIX, "event: connection_info —", info);
      });
      this.client.on("video_info", (info) => {
        console.log(LOG_PREFIX, "event: video_info —", info);
      });
      this.client.on("unknown", (message) => {
        console.log(LOG_PREFIX, "event: unknown —", message);
      });

      console.log(LOG_PREFIX, "calling client.start() — waiting for first video frame");
      await this.client.start();
      console.log(LOG_PREFIX, "client.start() resolved — connected");
      this._setState("idle");
    } catch (error) {
      console.error(LOG_PREFIX, "connect() failed:", error);
      this._setState("error");
    }
  }

  think() {
    console.log(LOG_PREFIX, "think() — state -> thinking");
    this._setState("thinking");
  }

  async speak(text, voiceId) {
    console.log(LOG_PREFIX, "speak() called, client connected:", !!this.client, "text length:", text.length);
    if (!this.client) {
      console.warn(LOG_PREFIX, "speak() called but no client connected yet — skipping");
      return;
    }

    this._setState("thinking");
    try {
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
      this.client.sendAudioData(new Uint8Array(buffer));
      console.log(LOG_PREFIX, "audio data sent to Simli client");
    } catch (error) {
      console.error(LOG_PREFIX, "speak() failed:", error);
      this._setState("error");
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
