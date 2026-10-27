# Branch and merge exercise

The two standalone websites were developed in sequence in `Week-5-task-1`. Their feature branches remain available for inspection.

1. Created `text-to-speech` from the original `main` commit `4bcb56b`.
2. Implemented the text-to-speech Flask website, passed 51 backend tests, and verified live Azure synthesis, browser playback, WAV download, and mobile layout.
3. Pushed feature commit `6cb170e` to `origin/text-to-speech`, merged it into `main` with merge commit `79012e6`, and pushed `main`.
4. Created `speech-to-text` after that merge, explicitly from original commit `4bcb56b`. Starting at that common baseline allowed the second implementation to independently add the same application files, producing the intentional conflict.
5. Implemented the speech-to-text Flask website, passed 61 backend tests, and verified live Azure transcription, MP3 normalization, microphone recording, transcript editing/copy/download, and mobile layout.
6. Pushed feature commit `1c55cce` to `origin/speech-to-text`. On `main`, ran `git merge --no-ff speech-to-text`. Git exited with status 1 and reported actual add/add conflicts in:
   - `README.md`
   - `app.py`
   - `speech.py`
   - `static/app.js`
   - `static/styles.css`
   - `templates/index.html`
7. Resolved the conflicts by combining both Flask endpoints, preserving one Azure request/error handler, retaining both test suites, and sharing the visual layout and stylesheet. Each feature has its own template and JavaScript file, with accessible tabs in the unified website. The final merge is committed and pushed to `main` after verification.

The original standalone features can be inspected with `git show text-to-speech:Week-5-task-1/app.py` and `git show speech-to-text:Week-5-task-1/app.py`. To see the final two-parent merge history, run:

```bash
git log --graph --oneline --decorate main text-to-speech speech-to-text
```

Final verification: **112 backend tests passed**. The unified website completed a live Azure text → WAV → transcript round trip. Browser checks covered both modes at 320, 390, 768, 980, and 1440 pixel widths, accessible keyboard tabs and links, and microphone cleanup when switching modes or cancelling a pending permission request.
