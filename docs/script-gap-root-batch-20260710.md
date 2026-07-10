# Xenari Script Gap Root Batch - 2026-07-10

Source: five uploaded screenplay files, filtered through `xenari_tool.py gaps` and the coinable-candidate triage.

Result:

- Added 57 new roots.
- Added 149 English mappings.
- Reused existing roots for 8 duplicate-ish candidates instead of coining duplicates.
- Regenerated `data/xenari-dict.json` and synced the site dictionary exports.

## New Roots

### Science, Space, And Reality

- `xrane` - inversion, reversal of direction, flow, or causality
- `qlutho` - entropy, disordering decay, irreversible loss of usable order
- `prulom` - plutonium, dense radioactive actinide metal
- `kulvex` - asteroid, small rocky body orbiting in space
- `xromel` - antimatter, matter with opposite charge structure
- `qorath` - radioactive, emitting ionizing radiation

### Technology And Devices

- `zecvar` - turnstile, rotating threshold or inversion gate
- `fexra` - reactor, controlled energy-reaction vessel or facility
- `thezru` - hearing aid, worn device that assists hearing
- `nexavo` - artificial intelligence, made mind or machine cognition
- `zilov` - earpiece, small device worn at or in the ear
- `nethru` - receiver, device or person that receives a signal or object
- `daxmel` - payload, carried cargo of a craft, tool, or weapon
- `zathor` - beacon, signal light or guiding transmitter

### Medicine And Body

- `nuzek` - respirator, breathing support mask or device
- `sqava` - syringe, injection tube with plunger and needle
- `klorun` - insulin, blood-sugar regulating hormone or medicine
- `thivan` - gurney, wheeled medical transport bed
- `qlavor` - bruise, dark injury mark under skin
- `dronel` - stethoscope, listening tool for heart and breath
- `murlaf` - deep breath, deliberate full inhale
- `nuvosh` - sweaty, wet with sweat

### Places, Props, And Objects

- `zroth` - aisle, narrow passage between rows or seats
- `axve` - silo, tall storage tower for grain or material
- `cavu` - yacht, private leisure boat or luxury vessel
- `zrelo` - freeport, bonded storage zone outside normal customs flow
- `nuvra` - peephole, small hole for looking through a barrier
- `xunel` - headstone, grave marker for the dead
- `cavrel` - paintbrush, handled brush for applying pigment
- `teksav` - clipboard, portable writing board with a clamp
- `savlo` - lantern, carried or enclosed light source

### Social, Legal, Crime, And Conflict

- `voshtek` - drug dealer, illicit seller of medicines or narcotics
- `cexu` - siege, surrounding pressure against a defended place
- `vepra` - defuse, make a bomb or danger unable to explode
- `satho` - lockdown, emergency sealed security state
- `qelvar` - appraisal, judged value or formal valuation
- `zuneth` - authentication, proof that something is genuine
- `qorvel` - provenance, recorded origin and ownership history
- `trezun` - hostage, captive held as leverage

### Mind, Emotion, And Qualities

- `vruska` - abandonment, being left behind or forsaken
- `zupel` - amnesia, loss or rupture of memory
- `dravun` - quizzical, puzzled in an openly questioning way
- `qrova` - agitated, stirred into restless distress
- `flunor` - vacant, empty, unoccupied, or blankly absent
- `volqen` - skeptical, doubtful and withholding belief
- `savren` - convinced, settled into belief or certainty
- `zerkul` - electrified, charged with or powered by electricity

### Sound And Voice

- `glivun` - whirr, steady rotary machine sound
- `qelto` - whoosh, rushing air or fast passing sound
- `sqor` - rustle, soft dry brushing movement sound
- `zavi` - swish, soft fast sweeping sound
- `xeha` - huh, questioning or confused vocalization
- `ux` - uh, hesitation filler vocalization
- `aza` - ah, soft realization, pain, or release vocalization
- `shava` - shhh, quieting hush vocalization
- `oxu` - ouch, pain interjection
- `vrumo` - whummmmm, low sustained machine or energy hum

## Mapped To Existing Roots

These were candidates from the harvest, but canon already had usable roots under related forms, so they got English mappings instead of duplicate roots.

- `drip` -> `priva` (already had `dripping`)
- `whoa` -> `vrifvluq` (already had `woah`)
- `negotiation` -> `kakarz` (already had `negotiate`)
- `inspection` -> `yetpecu` (already had `inspect`)
- `forgery` -> `zelesqe` (already had `forge`)
- `smuggling` -> `smuqo` (already had `smuggle`)
- `teary` -> `svir` (already had `tearful`)
- `detonation` -> `vloncvit` (already had `detonate`)

## Validation

- `pytest -q` - 19 passed
- `python3 xenari_tool.py doctor` - ok
- `python3 xenari_tool.py parity` - ok
- `npm run test:xenari` - passed

