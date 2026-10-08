<script>

const startBtn = document.getElementById("startBtn");
const status = document.getElementById("status");
const transcript = document.getElementById("transcript");

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

let recognition;
let isListening = false;


if (!SpeechRecognition) {

    status.innerText =
        "❌ Speech recognition is not supported. Please use Google Chrome.";

    startBtn.disabled = true;

} else {

    recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";


    // START / STOP BUTTON

    startBtn.onclick = function () {

        if (!isListening) {

            recognition.start();

        } else {

            recognition.stop();

        }

    };


    // WHEN MICROPHONE STARTS

    recognition.onstart = function () {

        isListening = true;

        startBtn.innerText =
            "🛑 Stop Speaking";

        status.innerText =
            "🎤 Listening... Speak now!";

    };


    // GET SPEECH

    recognition.onresult = function (event) {

        let text = "";

        for (
            let i = 0;
            i < event.results.length;
            i++
        ) {

            text +=
                event.results[i][0].transcript + " ";

        }

        transcript.innerText = text;

    };


    // WHEN MICROPHONE STOPS

    recognition.onend = function () {

        isListening = false;

        startBtn.innerText =
            "🎤 Start Speaking";

        status.innerText =
            "✅ Recording stopped.";

    };


    // ERROR

    recognition.onerror = function (event) {

        console.log(
            "Speech recognition error:",
            event.error
        );

        isListening = false;

        startBtn.innerText =
            "🎤 Start Speaking";

        status.innerText =
            "❌ Error: " + event.error;

    };

}

</script>