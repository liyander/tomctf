import CTFd from "../../index";

// List of audio files to play for First Blood events
// Place these files in assets/sounds/first_blood/
const FILES = [
    "spider.mp3",
];

// Path to the sounds directory (relative to web root)
// This should match the output path in vite.config.js
// Ensure this path is correct for your deployment
const SOUND_PATH = "/themes/tomctf-2026/static/sounds/first_blood/";

export default () => {
    // Hook into the eventToast function which handles notifications
    const originalToast = CTFd._functions.events.eventToast;
    const originalAlert = CTFd._functions.events.eventAlert;

    // Expose for testing in console: window.testFirstBloodSound()
    window.testFirstBloodSound = () => {
        console.log("[Sounds] Testing First Blood sound...");
        playRandomSound();
    };

    const checkAndPlay = (data) => {
        if (!data) return;

        // Combine all potential text fields
        const textContent = [
            data.title,
            data.html,
            data.content,
            data.message
        ].filter(Boolean).join(" ").toLowerCase();

        // Check if this is a First Blood notification
        if (textContent.includes("first blood")) {
            console.log("[Sounds] First Blood detected! Playing sound.");
            playRandomSound();
        }
    };

    CTFd._functions.events.eventToast = (data) => {
        checkAndPlay(data);
        // Call the original handler to show the toast
        if (originalToast) {
            originalToast(data);
        }
    };

    CTFd._functions.events.eventAlert = (data) => {
        checkAndPlay(data);
        // Call the original handler to show the alert
        if (originalAlert) {
            originalAlert(data);
        }
    };
};

function playRandomSound() {
    // If no files defined, do nothing
    if (FILES.length === 0) {
        return;
    }

    const randomFile = FILES[Math.floor(Math.random() * FILES.length)];
    const audioPath = `${SOUND_PATH}${randomFile}`;
    
    const audio = new Audio(audioPath);
    audio.volume = 0.6; // Adjust volume as needed
    
    // Play with user interaction handling
    audio.play().catch(error => {
        console.warn("[Sounds] Autoplay blocked or error:", error);
    });
}
