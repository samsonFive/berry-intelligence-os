# Publication variety-name review repair

Publication Review could prefill a descriptive phrase before a crop name as a
new variety. Its case-insensitive three-word pattern accepted ordinary prose
while omitting selection codes containing digits or hyphens. Saving a cleared
Varieties field did not persist that correction, so reopening could restore the
suggestion.

Unknown names now remain qualified review candidates with a literal text span
and a visible title, summary, excerpt or captured-body basis. Naming cues and
selection codes support native-language names without classifying a candidate
as an established identity. Candidates reach the Varieties field only through
explicit selection or manual entry. Existing stored/manual values and reviewed
directory matches are preserved; provisional directory matches stay qualified.

Save uses the current edit form, including when JavaScript is unavailable.
Edited or explicitly empty variety values persist privately and suppress later
prefill. GET creates no entity. Publication still requires the existing human
review decision; a deliberately submitted new name remains an unverified entity,
and publication creates no Atomic Evidence or Fact automatically.

Deterministic regressions exercise descriptive prose, selection codes, quoted
Unicode names, source basis, existing identities, Save/reopen, clearing, validation
recovery and explicit publication. Source acquisition, source authenticity,
historical detection and broader company-news recall remain separate work.

This is implementation evidence. Production release and live verification remain
pending; private research and operational receipts are excluded from this repo.
