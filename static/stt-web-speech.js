(function () {
  "use strict";

  const LOG_PREFIX = "[WebSpeechSTT]";
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

  class WebSpeechSTT {
    static get isSupported() {
      return !!SpeechRecognitionImpl;
    }

    constructor({ onFinalResult, onError, onListeningChange } = {}) {
      this.onFinalResult = onFinalResult;
      this.onError = onError;
      this.onListeningChange = onListeningChange;
      this._recognition = null;
    }

    start() {
      if (!WebSpeechSTT.isSupported) {
        console.warn(LOG_PREFIX, "start() called but SpeechRecognition is not supported in this browser");
        return;
      }
      if (this._recognition) {
        console.warn(LOG_PREFIX, "start() called while already listening — ignoring");
        return;
      }

      const recognition = new SpeechRecognitionImpl();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        console.log(LOG_PREFIX, "started listening");
        if (this.onListeningChange) this.onListeningChange(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        console.log(LOG_PREFIX, "final transcript:", transcript);
        if (transcript && this.onFinalResult) {
          this.onFinalResult(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.warn(LOG_PREFIX, "error:", event.error);
        if (this.onError) this.onError(event.error);
      };

      recognition.onend = () => {
        console.log(LOG_PREFIX, "stopped listening");
        this._recognition = null;
        if (this.onListeningChange) this.onListeningChange(false);
      };

      this._recognition = recognition;
      recognition.start();
    }

    stop() {
      if (this._recognition) {
        this._recognition.stop();
      }
    }
  }

  window.MiniEchoSTT = { WebSpeechSTT };
})();
