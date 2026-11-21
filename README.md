# Night Dial for Wear OS

Analog watch face for the Google Pixel Watch 5 (Wear OS 7). It runs on any round Wear OS 6 or
later watch.

It is built with the [Watch Face Format](https://developer.android.com/training/wearables/wff)
(version 4), which Google requires for watch faces.

![Night Dial on the Wear OS 7 emulator](docs/screenshot.png)

*Test build (`./build.sh test`) on the Wear OS 7 emulator, at the test build's fixed time of
10:09:36.*

## The face

- **Dial:** an orange ring at the edge of the face: a dot for every minute, larger at the
  hours, and a triangle pointing inward at 12, 3, 6 and 9. Small orange hour numerals 1 to
  12 sit just inside it.
- **Hands:** dark hour and minute hands with straight sides that widen out from the hub to a
  point, a gray outline, a bordered orange insert and a gray center bar; a light gray seconds
  hand with a counterweight, ending just inside the ring; and a black hub with three gray
  rings.
- **Weather:** left of the center, a little low, from the watch's weather data: an orange icon for the
  condition (night versions after dark), the temperature (red above 90°F, blue below 40°F,
  orange between) and the condition's name. Without weather data, the sun and "--°".
- **Battery:** at the top, between the gauges: an orange battery with a segment lit for
  every 20% (rounded up), and the percentage below it. Both turn red below 20%.
- **Date:** a gauge in the 1:30 segment: gray tick marks and day names, SUN to SAT, around
  an arc open at the bottom, an orange pointer at today's on a light gray hub, and the day
  of the month in gray below the hub.
- **Heart rate:** a matching gauge in the 10:30 segment, from 0 to 220 bpm around a wider
  arc: a tick every 10, a label every 40, and the rate below the hub. Without a reading,
  "--" and the pointer at 0.
- **Always-on mode:** the dimmed ring and numerals, and the hour and minute hands with
  their orange hollowed out to an outline; no seconds hand, weather, battery or gauges.

## How it's built

Watch Face Format is declarative XML with no code. The layout is computed from the screen
radius, so `tools/generate.py` writes the XML and renders the images with Pillow: each is
drawn large, saved as a master in `build/masters/` for review, and scaled down to screen
size. Edit the script, not the generated files.

| File | Purpose |
|---|---|
| `tools/generate.py` | Writes `res/raw/watchface.xml` and the images in `res/drawable/` |
| `tools/fonts/` | Varela Round for the numerals, temperature and battery percentage, and Oswald for the gauges (both SIL Open Font License) |
| `build.sh` | Generate, build, install, test build, runtime log |
| `watchface/src/main/AndroidManifest.xml` | Package, Watch Face Format version 4, no code |
| `watchface/src/main/res/raw/watchface.xml` | The watch face (generated) |
| `watchface/src/main/res/xml/watch_face_info.xml` | Preview image and picker settings |
| `watchface/src/main/res/values/strings.xml` | Names shown in the picker and editor |
| `watchface/src/main/res/drawable/preview.png` | Picker and store preview (an emulator capture of the test build) |

## Build

Needs Android Studio (for its JDK; the Android SDK with API 36 platform and build tools), and
Python 3 with Pillow.

```sh
./build.sh          # generate and build the debug APK
./build.sh run      # also install it on the watch or emulator and make it the active face
./build.sh test     # the same with the hands frozen and sample weather, battery, date and heart rate, to check the layout
./build.sh release  # release bundle (.aab) for Google Play (set up release signing first)
./build.sh log      # the watch face runtime's log: XML and expression errors show up here
```

`./build.sh test` writes the normal XML back when it's done, so the frozen hands never stay
in the source. Run `./build.sh run` afterwards to put the live face back on the watch.

The project also opens in Android Studio, which checks the watch face XML as you edit it.

## Run on the emulator or the watch

- **Emulator:** create a Wear OS 7 large round device (Device Manager in Android Studio, or
  `avdmanager create avd -k "system-images;android-37.0;android-wear-signed;x86_64" -d wearos_large_round`),
  start it, then `./build.sh run`.
- **Pixel Watch 5:** turn on Developer options (Settings → System → About → Versions, tap
  Build number seven times), then Developer options → Wireless debugging → Pair new device.
  On the PC: `adb pair <ip>:<port>` with the shown code, then `adb connect <ip>:<port>` with
  the port shown on the Wireless debugging screen, and `./build.sh run`.

A watch face changed with `./build.sh run` keeps its settings. To get the defaults again,
uninstall it first (`adb uninstall io.github.ls6777.nightdial`).
