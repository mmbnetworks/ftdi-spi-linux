## MMB Driver Updates

This repo makes some changes to help with GPIO timing. It also introduces DKMS
module builds so that the driver can be installed as a DKMS module. See
https://documentation.ubuntu.com/kteam-docs/public/tutorial/creating_dkms.html
for the process which was followed.

### Building the DKMS package

```sh
sudo apt-get install -y build-essential debhelper dh-dkms dkms
dpkg-buildpackage -us -uc -b
sudo dpkg -i ../ftdi-spi-linux_*_all.deb
```

Note that on Ubuntu 24.04 the `dh_dkms` helper and its debhelper sequence addon
live in the separate `dh-dkms` package -- they are no longer part of `dkms`
itself. The tutorial above predates that split, so following it verbatim gives
`dh: error: unable to load addon dkms`.

The build does not need `fakeroot`. `debian/control` sets
`Rules-Requires-Root: no`, so `dh_builddeb` passes `--root-owner-group` to
`dpkg-deb` and every path is recorded as `root:root` regardless of who runs the
build.

Verify the module was built and installed for the running kernel with:

```sh
dkms status ftdi-spi-linux
modinfo spi-ft232h
```

### Module loading

The driver is a USB driver with a `MODULE_DEVICE_TABLE`, so udev loads and binds
it automatically when a matching device appears. No `/etc/modules-load.d/` entry
is needed, and no udev rule needs to call `modprobe` or write to `new_id`.

Autoloading only works for USB IDs listed in `ft232h_intf_table` in
`src/spi-ft232h.c`. A board whose PID is missing from that table will enumerate
with no driver bound and no entry in `modules.alias`, even though the driver is
installed correctly. Add the ID to the table rather than working around it with
a udev rule. Currently matched:

| VID:PID     | Device                                   |
|-------------|------------------------------------------|
| `0403:6011` | FT4232H (only when `ftdi_sio` is absent) |
| `0403:6014` | FT232H  (only when `ftdi_sio` is absent) |
| `0403:6900` | MMB Gen3 Wi-SUN mPCIe card (FT2232H)     |
| `2beb:0146` | GW16146                                  |

The 6011/6014 entries are compiled out when `CONFIG_USB_SERIAL_FTDI_SIO` is
enabled, because `ftdi_sio` claims those same IDs. `0403:6900` is an MMB PID that
`ftdi_sio` does not claim, so it is matched unconditionally.

### Module configuration

Module parameters belong in `/etc/modprobe.d/`, not in a udev rule. Create
`/etc/modprobe.d/spi-ft232h.conf`:

```
options spi_ft232h perf_profile=0 max_block=4096 flush_per_block=1 rx_retry_us=100 pipeline_depth=1 latency=1
```

Use the underscore spelling `spi_ft232h` here. The source file is `spi-ft232h.c`
and the installed module is `spi-ft232h.ko`, but the module's runtime name --
what `lsmod`, `/sys/module/` and `modprobe.d` use -- has the hyphen normalised to
an underscore.

An `options` line applies no matter what triggers the load: kernel autoload on
hotplug, an initramfs, or a manual `modprobe`. Setting parameters instead via a
udev `RUN+="modprobe spi_ft232h <params>"` rule is fragile, because the kernel
autoloads the module from the interface `MODALIAS` as soon as the device
appears. Whichever loader runs first wins, and the loser is a silent no-op --
`modprobe` does not apply parameters to an already-loaded module. The failure
mode is not an error; the driver simply runs with default timings.

Parameters are only read at module load. To apply a change:

```sh
sudo modprobe -r spi_ft232h && sudo modprobe spi_ft232h
```

#### Checking the current settings

```sh
sudo systool -v -m spi_ft232h          # from the sysfsutils package
```

or directly from sysfs:

```sh
sudo sh -c 'for p in /sys/module/spi_ft232h/parameters/*; do
  printf "%-16s = %s\n" "$(basename $p)" "$(cat $p)"; done'
```

`sudo` is required. Most of these parameters are mode `0600`; read as a normal
user they come back as empty strings rather than a permission error, which looks
like "unset" and is easy to misread.

Related commands:

```sh
modinfo -p spi-ft232h                                   # available parameters
sudo dmesg | grep -E 'spi_probe|gpio-irq polling'       # values active at probe
sudo cat /sys/kernel/debug/ftdi_spi/spi-ft232h.0/stats  # live perf counters
```

Note that `enable_stats` defaults to **on** (`param_enable_stats = true`),
despite its `MODULE_PARM_DESC` text claiming "default disabled". Add
`enable_stats=0` to the options line to turn metrics collection off.

#### Files in `src/` that are deliberately not packaged

`src/` carries two modprobe snippets inherited from upstream. Neither is
installed by the DKMS package, and that is intentional:

| File | Contents | Why it is not installed |
|------|----------|-------------------------|
| `src/spi-ft232h.conf` | `softdep spi_ft232h post: nrc` | Loads the Newracom `nrc` driver after this one. `nrc` is not present on MMB Gen3 hardware, so the softdep has nothing to resolve. |
| `src/blacklist-ftdi_sio.conf` | blacklists `ftdi_sio` | Only needed for boards using the `0403:6011`/`6014` IDs, which this driver compiles out when `CONFIG_USB_SERIAL_FTDI_SIO` is enabled. The MMB PID `0403:6900` is not claimed by `ftdi_sio`. |

**Do not install `src/spi-ft232h.conf` to `/etc/modprobe.d/`.** It shares a
basename with the options file described above, so packaging it under that path
would overwrite the deployed parameter tuning with an unrelated softdep line. If
the softdep is ever genuinely needed, install it under a distinct name such as
`/etc/modprobe.d/ftdi-spi-linux-softdep.conf`.

### Building out-of-tree (without DKMS)

The module sources live in `src/`:

```sh
make -C src                 # builds src/spi-ft232h.ko and src/spi-ft232h.ko.zst
sudo make -C src modules_install
```
