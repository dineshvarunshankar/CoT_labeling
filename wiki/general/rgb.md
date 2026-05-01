---
id: rgb
scope: general
---

# rgb

## Human Findings

### 001 - RGB preserves color and surface detail

RGB images preserve color, geometry, clothing texture, shadows, and visible
surface detail. They can support reasoning about blood color, limb outlines,
posture, hand placement, and object contact.

### 002 - RGB can be degraded by lighting and blur

RGB interpretation can be degraded by low light, motion blur, sun glare, heavy
shadow, and tinted field lighting.

### 003 - RGB spatial evidence should stay tied to the target subject

When RGB images show multiple people or busy backgrounds, reason about objects,
fluid flow, hands, limbs, and support surfaces only when they are inside the target
box or clearly connected to the boxed subject.

### 004 - RGB color alone is not enough

Color can suggest blood, clothing, equipment, or lighting artifacts, but the CoT
should combine color with shape, location, contact, pooling pattern, or body
part continuity before treating it as decisive evidence.

## Agent Findings
