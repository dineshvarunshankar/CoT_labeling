---
id: subject_types
scope: general
---

# subject_types

## Human Findings

### 001 - Subject type affects posture interpretation

The target bbox may contain a live actor, manikin, medic/non-casualty, or
robotic surrogate. Interpret posture and triage evidence in light of the visible
subject type, especially for `medic_noncasualty`.

### 002 - Only the boxed subject determines the answer

Other people, medics, robots, or objects may provide context, but the answer must
be based on the target subject in the box. Do not transfer another person's
posture, injury, or role to the boxed subject.

### 003 - Non-biological subjects can mimic casualty posture

Manikins and robotic surrogates may have stiff joints, uniform thermal texture,
or angular silhouettes. Use visible body layout and contact geometry, not assumed
human motion or physiology, when reasoning about them.

## Agent Findings
