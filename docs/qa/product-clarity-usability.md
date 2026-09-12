# Product clarity usability study

Status: protocol ready; participants have not been recruited or observed. Automated fixtures and agent reviews are not participant results.

## Purpose

Evaluate whether the companion helps unfamiliar Codex users interpret quota, notice required input and return to the intended task with tolerable desktop obstruction. This is formative research, not a market-size or retention study.

Recruit five willing people who use Codex but have not used this companion. Record their usual number of parallel tasks, preferred display size/scaling and whether they normally keep Codex visible. Obtain consent for observation and any recording. Use sample task names and accounts; never ask participants to spend a real reset credit or disclose conversation contents. Keep identifying information outside Git.

## Session

Allow about 20 minutes per person. Explain that the interface is being tested, not the participant. Begin with the fresh-install defaults, then use a safe prepared sample state. Do not explain labels, click targets or the statistics toggle before the relevant task. Permit stopping at any time.

1. **Interpret capacity and freshness.** Show remaining Week/5h quota, observed Today consumption and an afternoon observation start. Ask what each number represents and what earlier usage is covered. Then show a failed quota refresh and an expired 5h panel; ask whether the displayed data is current and what they would trust.
2. **Respond to a task.** Present several Running tasks and one Needs input item. Ask which task requires them now and have them return to it. Use mocked navigation or their own explicitly authorized test task, with no actual approval or reset operation.
3. **Recover an older task.** Give a project and partial task title. Ask them to find and open the correct record. Next ask for its available historical Token total, observing whether they discover History statistics without being told where it is.
4. **Reduce desktop obstruction.** Ask them to hide the Running title strip while keeping status counts. Reopen and reposition the title strip, then hide it again. Check whether placement and topmost scope are understood.

After the tasks, compare the one-strip default with the optional title strip in the same work context. Vary which arrangement is tried first across participants. Ask what they would leave enabled during ordinary work and why. A preference is not an efficiency result.

## Record for each task

| Anonymous participant | Task | Completed independently / with help / failed | Time | First interpretation | Errors or wrong destination | Assistance | Comments |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Not yet observed | — | — | — | — | — | — | — |

Record observation-start and freshness misunderstandings separately from navigation errors. Record accidental openings, repeated hovering while waiting for a title, obstruction of another control, and whether the participant disables the title strip. Do not infer success from an attractive screenshot or a verbal compliment.

## Decisions after observations

- Repeated incorrect interpretation of remaining/observed consumption, cached values or inferred reset sources requires a wording/placement revision before stronger product claims.
- Difficulty finding the action-needed task takes priority over decorative changes or additional statistics.
- Prefer the least obstructive default that preserves successful state recognition. Do not reverse existing users' saved presentation choices based on five sessions.
- Inspect failures individually before aggregating time or success counts; report assistance and incomplete sessions. This small study does not establish population percentages.

## Current delivery boundary

The engineering release validates calculations, interaction contracts, installation and controlled layouts. This study remains pending until real willing participants are available. No invitation has been sent, no telemetry added and no participant results claimed.
