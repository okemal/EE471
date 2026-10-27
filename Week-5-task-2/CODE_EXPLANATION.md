# Voice Calculator: Code Block Walkthrough

This document follows the logical blocks in each application and test file. Function names and selectors identify the corresponding source without duplicating entire files. For setup, commands, API examples, and troubleshooting, see [DOCUMENTATION.md](DOCUMENTATION.md).

## 1. `app.py`: Flask entry point

### Imports

`math` checks whether numeric values are finite. `Path` locates configuration files. Flask provides application creation, JSON responses, template rendering, and the current request. `load_dotenv` loads local environment configuration. `Calculator` supplies arithmetic, while `SpeechError`, `recognize`, and `synthesize` provide the speech boundary.

### Environment file search

The `for directory in Path(__file__).resolve().parents` block searches the script's containing directory and then its ancestors. The first `.env` file found is loaded, and `break` ends the search. Values already present in the process environment are preserved by `load_dotenv`'s default behavior. No credential values are included in HTML or JavaScript.

### Application creation and request limit

`Flask(__name__)` creates the web application and lets Flask locate its `templates` and `static` directories. `MAX_CONTENT_LENGTH` sets a global 512 KiB request body limit, including audio uploads.

### `speech_error(error)`

The `@app.errorhandler(SpeechError)` decorator registers a shared exception handler. It converts an intentional speech failure into a JSON `error` field and uses the exception's HTTP status. Speech functions can therefore raise one consistent exception type instead of constructing Flask responses themselves.

### `speech_recognize()`

The `POST /api/speech/recognize` route checks that the request MIME type is `audio/wav`. It passes raw request bytes to `recognize()`, then returns the transcript as JSON. `Cache-Control: no-store` asks HTTP caches not to retain the response. A wrong MIME type returns `400` before contacting Azure.

### `speech_speak()`

The `POST /api/speech/speak` route reads JSON without raising a Flask JSON parsing error for malformed input. It extracts `text` only from a dictionary; otherwise it passes `None` to validation. `synthesize()` returns MP3 bytes, which the route sends as `audio/mpeg` with `Cache-Control: no-store`.

### `calculator()`

The `GET /` route renders `index.html`. Jinja resolves static asset URLs while rendering the template.

### `calculate()`: request validation

The first part of `POST /api/calculate` requires a JSON object, one of four operator strings, and a list containing exactly two numbers. It explicitly rejects booleans because Python treats `bool` as a subclass of `int`. Values are converted to floats and checked with `math.isfinite()` so infinities and NaN are not accepted.

### `calculate()`: dispatch and result

A new `Calculator` instance is created for the request. The `operations` dictionary maps operator strings to bound arithmetic methods. Calling `operations[operator](left, right)` selects the requested calculation. A `ValueError`, including division by zero, becomes a `400` JSON error. A final finite check rejects an out-of-range result; otherwise the route returns `result`.

### Main guard

`if __name__ == '__main__': app.run()` starts the local server when the file is executed directly. Importing `app` in tests does not start a server.

## 2. `speech.py`: Azure integration

### Imports and module boundary

`io` and `wave` inspect audio in memory. `json` decodes recognition results. `os` accesses environment variables. `re` validates strings. `urllib` constructs HTTPS requests and identifies network failures. `escape` protects XML text used in SSML. These utilities come from Python's standard library.

### `SpeechError`

This exception stores a user-facing message and an HTTP status, defaulting to `502`. Its constructor passes the message to `Exception` and keeps `status` for Flask's error handler.

### `azure_request()`: configuration and request construction

The function selects `AZURE_API_KEY_1`, falling back to `AZURE_SPEECH_KEY`. It strips and validates the region using a lowercase letter/digit/hyphen pattern. Missing configuration produces `503`.

The request URL uses the region, service (`stt` or `tts`), and endpoint path. The subscription key is attached only to the outbound server request in the `Ocp-Apim-Subscription-Key` header. Content type and optional synthesis headers are also attached. The body is sent with `POST`.

### `azure_request()`: response and error handling

`urlopen(..., timeout=20)` sends the request and reads the returned bytes. The context manager closes a successful response. HTTP failures are explicitly closed and replaced with a generic `SpeechError`; network and timeout failures receive another generic message. `from None` suppresses exception chaining, and upstream response bodies or request objects are not forwarded to the browser.

### `recognize()`: WAV validation

`wave.open(io.BytesIO(audio), 'rb')` reads the supplied WAV without creating a disk file. The validation block requires one channel, two-byte samples, a 16 kHz sample rate, and a positive frame count no greater than 12 seconds. Reading the frames also checks that the body contains the declared sample bytes. Invalid audio produces a `400` error before an Azure request.

### `recognize()`: Azure request

The recognition call selects `en-US` and `format=detailed` in the endpoint query string. Its content type describes WAV PCM sampled at 16 kHz. `azure_request()` returns the JSON response as bytes.

### `recognize()`: transcript extraction

`json.loads()` decodes the response. A status other than `Success` produces `422` with retry guidance. The first entry in `NBest` supplies its `Lexical` text, preserving recognized command words such as “three” rather than relying on display normalization. Missing fields, malformed JSON, unexpected structures, or blank transcript values produce a sanitized `502` error.

### `synthesize()`: input validation

The function accepts a nonblank string of at most 200 characters. Its regular expression limits text to calculator announcement characters and rejects markup. Invalid input produces `400`.

### `synthesize()`: SSML and output format

The text is XML-escaped and inserted inside `<speak>` and `<voice>` elements. The selected voice is `en-US-JennyNeural`. The synthesis request specifies `application/ssml+xml` input and `audio-24khz-48kbitrate-mono-mp3` output. The returned bytes are passed back to the Flask route.

## 3. `custom_classes.py`: arithmetic

| Code block | Explanation |
| --- | --- |
| `class Calculator` | Groups the four arithmetic operations. |
| `__init__()` | Initializes `_current_val` to `0.0`. The underscore marks it as internal by convention. |
| `add(x, y)` | Stores `x + y` and returns it. |
| `subtract(x, y)` | Stores `x - y` and returns it. |
| `multiply(x, y)` | Stores `x * y` and returns it. |
| `divide(x, y)` | Rejects a zero divisor with `ValueError`, then stores and returns `x / y`. |

Each method updates the instance's last value. Web requests use explicit operands and a fresh instance, so this field does not persist browser state between requests.

## 4. `main.py`: original demonstration

The script imports and constructs `Calculator`, adds `10` and `5`, multiplies the stored result by `2`, and divides that result by `3`. Printing `_current_val` produces `10.0`. This is a standalone demonstration; the Flask page does not call it.

## 5. `static/js/calculator.js`: calculator state and input

### Import and enclosing function

The module imports `createVoice`, `digitWords`, and `spokenNumber` from `speech.js`. The immediately invoked function `(() => { ... })()` runs the setup once and keeps its variables scoped to the calculator.

### DOM references and state variables

The first block locates the result, expression, and keypad elements.

| Variable | Purpose |
| --- | --- |
| `current` | Current display value as a string, preserving entries such as `0.`. |
| `stored` | Left operand waiting for an operation, or `null`. |
| `operator` | Pending arithmetic operator, or `null`. |
| `replaceCurrent` | Makes the next digit start a new entry. |
| `justEvaluated` | Marks the display as the outcome of an evaluation rather than editable input. |
| `waitingForCalculation` | Prevents overlapping input during an arithmetic request. |
| `voiceBusy` | Prevents manual calculator input while recording or processing voice input. |

### `createVoice()` callbacks

`onBusy` changes `voiceBusy` and refreshes the controls. `onCommands` receives an already validated key sequence, awaits `press()` for each key, and stops if the calculator reaches `Error`. Awaiting each command preserves operation order across asynchronous HTTP requests.

### `operatorSymbols` and `render()`

The symbol map converts internal `*` and `/` operators to their display forms. `render()` writes `current` to the display, disables keypad buttons while busy, updates microphone availability through `setCalculating()`, and toggles the operator button's `is-selected` CSS class according to the pending operator and entry state.

### `format(value)`

Non-finite values become `Error`. Finite values are rounded to 12 significant digits and converted back to a compact string. This reduces floating-point display artifacts and limits result length.

### `inputDigit(digit)`

A digit replaces an error, completed result, or value marked for replacement. Otherwise it replaces an initial zero or appends to the current entry, subject to the length check. Editing a number as text allows a decimal point to remain visible before another digit is entered.

### `requestCalculation(left, right, operation)`

This helper posts JSON to `/api/calculate`, decodes its JSON response, throws the server's error message when unsuccessful, and returns the numeric result on success. Arithmetic stays in the Python `Calculator` class.

### `chooseOperator(nextOperator)`

The displayed value becomes the left operand. If an earlier operator already has both operands, that calculation is completed first. Busy flags and `render()` disable input while waiting. On success, the new operator and expression are stored, and the next digit is marked to replace the display. On failure, pending arithmetic is cleared and the display enters the error state. The `finally` block releases the arithmetic busy flag.

### `equals()`

With no pending operation, the function returns. Otherwise it snapshots both operands and the operator, shows the completed expression, clears pending arithmetic, and requests the result. A failure displays `Error` with the error message in the expression area. Its `finally` block restores controls and renders the result.

### `applyPercent()`

This function divides the current number by `100` using the same calculation endpoint. It follows the same busy, error, and cleanup pattern as ordinary arithmetic.

### `clear()`

The display returns to `0`, both pending operands/operator state are cleared, entry flags reset, and the expression line is emptied.

### `act(action)`

This block handles non-digit actions. Decimal input starts `0.` when a fresh entry is needed and otherwise adds a point only if none exists. Sign toggles a leading minus for nonzero, non-error values. Percent and equals await their asynchronous helpers. Backspace shortens editable input and uses `0` when deleting the last digit or leaving only a minus sign. The function then refreshes the display.

### `press(key)`

This is the shared entry point for mouse, keyboard, and recognized voice commands. Digits call `inputDigit()`, operators await `chooseOperator()`, and other keys map to actions in `act()`. Each branch constructs its announcement. Equals uses `is ${spokenNumber(current)}` after the result is available. Errors announce the expression's error message instead. Finally, it renders and queues speech.

### Keypad click handler

Event delegation finds the closest clicked button. Busy input is ignored. The handler resumes browser audio after the user gesture, translates the button's `data-*` attribute into a key, and calls `press()`. A failed audio unlock is caught so it does not prevent calculator input.

### Keyboard handler and initial render

The keyboard handler ignores calculator commands while busy, recognizes supported keys, and prevents their usual browser behavior. Enter on a focused button is left to the button's native behavior. Valid shortcuts resume audio and call `press()`. The last `render()` initializes the page's visible state.

## 6. `static/js/speech.js`: speech and audio controller

### `digitWords` and `commands`

`digitWords` provides names for digits. `Object.fromEntries()` builds the reverse mapping from spoken words to key strings. `Object.assign()` adds arithmetic and utility commands. Both spoken input and spoken output therefore use the required vocabulary.

### `parseCommands(text)`: normalization

The function lowercases and trims the transcript, joins “change sign” into a single token, removes selected punctuation, and strips a trailing sentence period. The result is split into whitespace-separated tokens.

### `parseCommands(text)`: token validation

Each token must be a mapped command word, the change-sign token, a numeric token, or a supported operator symbol. Numeric tokens such as `12.5` expand into individual key characters. Unknown tokens throw immediately. The completed list is returned only after validation, with a maximum of 60 keys. Consequently no commands execute from a rejected phrase.

### `spokenNumber(value)`

This helper maps characters to spoken digit names, `minus`, or `point`, then joins them with spaces. Scientific notation's `e` becomes “times ten to the power.” Values are read digit by digit, not converted into words such as “twelve.”

### `encodeWav(chunks, sampleRate)`: collecting samples

AudioWorklet messages arrive as floating-point chunks. This function totals their lengths and copies them into one `Float32Array`. It calculates how many output samples represent the same duration at 16 kHz.

### `encodeWav(chunks, sampleRate)`: WAV header

An `ArrayBuffer` reserves 44 bytes for the header plus two bytes per output sample. `DataView` writes `RIFF`, `WAVE`, `fmt `, and `data` fields, along with PCM format, one channel, 16 kHz sample rate, 32,000 bytes per second, two-byte block alignment, and 16-bit depth. Multibyte numeric fields are little-endian, as required by this WAV format.

### `encodeWav(chunks, sampleRate)`: sample conversion

For each output sample, the corresponding source interval is averaged when downsampling. Values are clamped to `[-1, 1]`, scaled to signed 16-bit integers, and written after the header. The returned buffer is ready to send as the request body.

### `createVoice()`: DOM references and controller state

The factory receives `onBusy` and `onCommands` callbacks, then finds the microphone and status elements. Its local variables track the shared audio context, playback promise queue, cancellation generation, currently playing source, recording session, startup/processing flags, and decoded-audio cache.

### `message`, `unlock`, and `cancelSpeech`

`message()` updates status with `textContent`, treating transcripts as plain text. `unlock()` creates an audio context when needed and resumes it. `cancelSpeech()` advances a generation counter and stops current playback. Older queued work compares its saved generation before playback and skips itself when obsolete; a request already in flight is not explicitly aborted by this function.

### `speak(text)`: queue and cache

Each announcement chains work onto `queue`, keeping playback ordered. The task checks its generation, resumes audio, and looks for a decoded buffer in the cache. Missing announcements are fetched from `/api/speech/speak` with a 25-second timeout, decoded, and cached. At 64 entries, the oldest inserted cache entry is removed before adding another; cache hits do not change insertion order.

### `speak(text)`: playback and failure

After a second generation check, an `AudioBufferSourceNode` plays the buffer through the output device. A promise resolves when playback ends, allowing the next queued announcement to start. The ended handler disconnects the source. Errors become a status message, and the caught promise allows later announcements to continue.

### `finish()`: stop recording and release resources

The function snapshots the active session and returns if there is none. It clears `recording` immediately to prevent duplicate processing, sets the processing flag, cancels the timer, removes the message callback, disconnects audio nodes, and stops every microphone track. The microphone's accessibility state resets and the status becomes “Recognizing…”. Resources are released before the network request.

### `finish()`: recognition and command dispatch

Recorded chunks are encoded as WAV and posted to `/api/speech/recognize` with a 25-second timeout. The returned text is fully parsed before `onCommands(keys)` executes it. Recognized text appears in the status area. Errors display an appropriate message. The `finally` block clears processing, calls `onBusy(false)`, and restores the microphone button.

### Microphone click handler: branching and startup

A click during recording calls `finish()`. A click during startup returns. Unsupported microphone/audio APIs produce a status message. Otherwise startup is marked busy, current speech is cancelled, and microphone access is requested with mono audio, echo cancellation, and noise suppression preferences.

### Microphone click handler: audio graph and session

The recorder worklet module is loaded relative to `speech.js`. A media stream source connects to an `AudioWorkletNode`. The session stores nodes, stream, chunks, frame count, timing information, and whether sound has been heard. Connecting the worklet to the destination keeps the graph active; the processor does not copy microphone samples to its output.

### Worklet message handler: silence detection

Incoming chunks are saved and frame counts are converted into elapsed audio time. Root mean square (RMS) measures chunk volume. RMS above `0.015` marks sound and updates its timestamp. After sound has occurred, more than `1.4` seconds below the threshold ends recording. This detects volume, not whether a chunk contains a spoken word.

### Microphone timer, accessibility state, and startup errors

A 10-second timer limits each recording independently of silence detection. The button becomes pressed with a “Finish voice command” label while listening. Startup failures stop any acquired tracks and distinguish permission denial from other device errors. Busy state and the disabled button are restored in cleanup.

### Returned controller interface

The factory returns `speak`, `unlock`, `cancelSpeech`, and `setCalculating`. The calculator uses the last method to disable the microphone during arithmetic or speech processing, while leaving an active recording's button available for manual completion.

## 7. `static/js/recorder-worklet.js`: audio processing thread

`RecorderProcessor` extends `AudioWorkletProcessor`. Its `process(inputs)` callback reads the first input channel, copies the samples, and posts them to the main thread through `this.port`. Returning `true` keeps the processor active. The method does not fill output channels, so it does not play the microphone back to the user.

`registerProcessor('calculator-recorder', RecorderProcessor)` registers the name used by `new AudioWorkletNode()` in `speech.js`.

## 8. `templates/index.html`: interface blocks

| Markup block | Explanation |
| --- | --- |
| Document declaration and `<head>` | Set HTML mode, English language, UTF-8, mobile viewport, theme color, and page title. |
| Stylesheet and module script | Use Flask's `url_for()` to load local assets. `type="module"` enables JavaScript imports and deferred execution. |
| `<main class="calculator">` | Provides the calculator's main semantic container and accessible name. |
| `.voice-controls` | Places the microphone beside the status text. The SVG draws the icon; `aria-hidden` avoids reading decorative shapes. |
| `#microphone` attributes | Provide an accessible label, pressed state, and association with the status explanation. JavaScript updates these during recording. |
| `#voice-status` | Uses `role="status"` so assistive technology can announce status changes. |
| `.display` | Contains the expression and result. `aria-live="polite"` and `aria-atomic="true"` expose updates to assistive technology. |
| `.keypad` | Contains all keys. `data-digit`, `data-operator`, and `data-action` supply machine-readable behavior separate from the visible symbol. |
| Keypad rows | Group utility keys first, then digits/operators, then backspace, zero, decimal, and equals. |
| Keyboard hint | Reminds the user about keyboard input. |
| `.voice-help` | A native expandable `<details>` element lists commands and explains how to finish a recording. |

## 9. `static/css/style.css`: style blocks

| Selector/block | Explanation |
| --- | --- |
| `:root` | Sets the light color scheme, base font, and default colors. |
| `*` | Uses `border-box` sizing so padding and borders fit within declared widths. |
| `body` | Centers the calculator, adds viewport padding, and paints the background gradient. |
| `.calculator` | Limits width to 340 pixels or available space and adds the blue card, rounded corners, and shadow. |
| `.display` | Arranges expression and result vertically at the bottom right of the white display. |
| `.voice-controls`, `.microphone`, `.microphone svg` | Lay out the microphone/status row and style the circular microphone control and icon. |
| Microphone pressed/focus/disabled rules | Show recording state, keyboard focus, and unavailable controls. The disabled selector also applies to calculator keys. |
| `#voice-status` | Formats status text and allows long messages to wrap. |
| `.voice-help` and child rules | Style expandable command help and its paragraphs. |
| `.expression` | Shows smaller, right-aligned expression text and truncates overflow. |
| `.result` | Uses a responsive large font and truncates values that exceed display width. |
| `.keypad` | Builds a four-column CSS grid with consistent gaps. |
| `.key` | Defines shared key dimensions, typography, colors, cursor, and interaction transitions. |
| Hover, active, and focus rules | Provide pointer, pressed, and keyboard-focus feedback. |
| `.key-function`, `.key-operator`, `.is-selected` | Distinguish function keys, arithmetic keys, and the selected operator style. |
| `.keyboard-hint` | Styles the small reminder below the keypad. |
| `@media (max-width: 380px)` | Reduces padding, gaps, and key height on narrow screens. |
| `@media (prefers-reduced-motion: reduce)` | Reduces transition duration for users requesting less motion. |

## 10. `requirements.txt`: dependencies

`Flask>=3.0,<4.0` supplies the web framework. `python-dotenv>=1.0,<2.0` supplies `.env` loading. Audio handling and HTTP calls on the server use the standard library; browser audio uses Web Audio APIs. No Azure SDK or frontend bundler is required by this implementation.

## 11. `tests/test_speech.py`: Python checks

### Imports, path setup, and `wav_audio()`

The test module imports standard test, mocking, audio, and error utilities. Adding the application directory to `sys.path` allows discovery from the repository root or calculator folder. `wav_audio()` creates one second of silence in memory with adjustable channel count and sample rate, providing both valid and deliberately invalid test inputs.

### `SpeechTests.setUp()`

Each test receives a fresh Flask test client. Routes can be exercised without starting a network server.

### Individual test blocks

| Test | What it verifies |
| --- | --- |
| `test_recognition_preserves_lexical_command_words` | The API chooses lexical text instead of normalized display text and sends `no-store`. |
| `test_invalid_audio_never_reaches_azure` | Invalid bytes, 8 kHz audio, and stereo audio return `400` without calling Azure. |
| `test_recognition_requires_wav` | A JSON request to recognition is rejected. |
| `test_no_match_is_actionable` | Azure's `NoMatch` produces a `422` response with retry guidance. |
| `test_malformed_upstream_response_is_sanitized` | Invalid Azure JSON becomes `SpeechError`. |
| `test_synthesis_returns_audio` | The route returns MP3 content type and includes announcement text in generated SSML. |
| `test_synthesis_rejects_markup_and_invalid_input` | Missing, blank, overly long, non-string, or markup text is rejected without an Azure request. |
| `test_upstream_failures_never_expose_credentials` | Mocked HTTP, network, and timeout failures return `502` without a deliberately planted dummy secret. |
| `test_missing_configuration_is_actionable` | Empty key variables produce `503`. |
| `test_arithmetic_and_division_by_zero` | All four operations return expected values and division by zero returns `400`. |

`@patch` replaces Azure calls or environment values for a test, keeping these checks offline. `unittest.main()` enables direct execution of the file.

## 12. `tests/commands.test.mjs`: JavaScript checks

The imports use Node's built-in test runner and strict assertions, then load the pure helpers from `speech.js`. Importing that module does not start browser recording; DOM access occurs only when `createVoice()` is called.

| Test block | What it verifies |
| --- | --- |
| Required digits and operations | Every specified command maps to the expected key. |
| Lexical phrases and normalized numbers | Punctuation, numeric transcripts, and utility commands parse correctly. |
| Unknown or empty phrases | Invalid input throws rather than returning a partial command sequence. |
| Spoken signs, decimals, and scientific notation | Character-based number announcements match the expected vocabulary. |
| WAV conversion | A second of 48 kHz input becomes a mono, 16 kHz, 16-bit WAV with the correct header, sample value, and byte length. |

## 13. Example execution: “three plus five is”

1. The microphone click handler acquires a stream and starts `RecorderProcessor`.
2. The worklet posts sample chunks; the main thread accumulates them until recording ends.
3. `finish()` stops the tracks, calls `encodeWav()`, and uploads the recording.
4. Flask calls `recognize()`, which validates the audio and asks Azure for a transcript.
5. `parseCommands()` converts the entire transcript into `['3', '+', '5', '=']`.
6. `onCommands` awaits four calls to `press()`. The plus command stores `3`; the next digit becomes `5`.
7. Equals sends the two operands to Flask, where `Calculator.add()` returns `8`.
8. `render()` displays `8`, and the playback queue speaks “three,” “plus,” “five,” and “is eight.”

Command execution and speech playback have separate ordering: each arithmetic command waits for the previous command, while each announcement waits for previous audio. Calculator input does not need to wait for all announcements to finish.
