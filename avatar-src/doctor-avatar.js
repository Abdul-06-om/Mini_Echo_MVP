import { SimliClient, LogLevel } from "simli-client";

export class DoctorAvatar {
  constructor({ videoEl, audioEl, panelEl, stateEl }) {
    this.videoEl = videoEl;
    this.audioEl = audioEl;
    this.panelEl = panelEl;
    this.stateEl = stateEl;
    this.client = null;
    this.state = "idle";
    this._setState("idle");
  }

  async connect() {
    this._setState("thinking");
    try {
      const response = await fetch("/avatar/session", { method: "POST" });
      if (!response.ok) {
        throw new Error("Failed to create avatar session");
      }
      const { session_token } = await response.json();

      this.client = new SimliClient(
        session_token,
        this.videoEl,
        this.audioEl,
        null,
        LogLevel.ERROR,
        "livekit",
      );

      this.client.on("speaking", () => this._setState("speaking"));
      this.client.on("silent", () => this._setState("idle"));
      this.client.on("error", () => this._setState("error"));

      await this.client.start();
      this._setState("idle");
    } catch (error) {
      console.error("DoctorAvatar: connect failed", error);
      this._setState("error");
    }
  }

  think() {
    this._setState("thinking");
  }

  async speak(text, voiceId) {
    if (!this.client) return;

    this._setState("thinking");
    try {
      const response = await fetch("/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(voiceId ? { text, voice_id: voiceId } : { text }),
      });
      if (!response.ok) {
        throw new Error("TTS request failed");
      }
      const buffer = await response.arrayBuffer();
      this.client.sendAudioData(new Uint8Array(buffer));
    } catch (error) {
      console.error("DoctorAvatar: speak failed", error);
      this._setState("error");
    }
  }

  _setState(state) {
    this.state = state;
    if (this.stateEl) {
      this.stateEl.textContent = state;
    }
    if (this.panelEl) {
      this.panelEl.dataset.state = state;
    }
  }
}
