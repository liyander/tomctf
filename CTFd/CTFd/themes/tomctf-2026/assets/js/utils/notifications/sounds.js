import CTFd from "../../index";

// List of audio files to play for First Blood events
const FILES = ["spider.mp3"];

// Path to the sounds directory (relative to web root)
const SOUND_PATH = "/themes/tomctf-2026/static/sounds/first_blood/";

// Keep a reference so the audio object is not garbage-collected before it finishes
let _lastAudio = null;

export default () => {
    // Hook into the eventToast function which handles notifications
    const originalToast = CTFd._functions.events.eventToast;
    const originalAlert = CTFd._functions.events.eventAlert;

    // Expose globally so challenges.js can call it on first_blood response
    window.testFirstBloodSound = () => {
        console.log("[Sounds] Triggering First Blood sound...");
        playRandomSound();
    };

    const checkAndPlay = (data) => {
        if (!data) return;

        // Combine all potential text fields
        const textContent = [
            data.title,
            data.html,
            data.content,
            data.message,
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

        // Check if this is a First Blood notification
        if (textContent.includes("first blood")) {
            console.log("[Sounds] First Blood detected via SSE! Playing sound.");
            playRandomSound();
        }
    };

    CTFd._functions.events.eventToast = (data) => {
        checkAndPlay(data);
        if (originalToast) {
            originalToast(data);
        }
    };

    CTFd._functions.events.eventAlert = (data) => {
        checkAndPlay(data);
        if (originalAlert) {
            originalAlert(data);
        }
    };
};

function playRandomSound() {
    if (FILES.length === 0) return;

    const randomFile = FILES[Math.floor(Math.random() * FILES.length)];
    const audioPath = `${SOUND_PATH}${randomFile}`;

    console.log("[Sounds] Loading audio:", audioPath);
    const audio = new Audio(audioPath);
    audio.volume = 0.7;

    // Keep reference to avoid GC
    _lastAudio = audio;

    audio.play().then(() => {
        console.log("[Sounds] Audio playing successfully.");
    }).catch(error => {
        console.warn("[Sounds] Autoplay blocked, will retry on next user interaction:", error.message);

        // Queue retry on next user interaction
        const retry = () => {
            audio.currentTime = 0;
            audio.play().catch(err => {
                console.warn("[Sounds] Retry failed:", err.message);
            });
            // Remove the other listener
            window.removeEventListener("click", retry, true);
            window.removeEventListener("keydown", retry, true);
        };

        window.addEventListener("click", retry, { once: true, capture: true });
        window.addEventListener("keydown", retry, { once: true, capture: true });
    });
}
