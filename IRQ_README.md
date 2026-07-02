# FT232H GPIO IRQ Path and Findings

## Summary

A kernel warning was observed:

- `irq <n> handler lineevent_irq_handler... enabled interrupts`
- warning site: `__handle_irq_event_percpu()`
- task context: `ftdi-irq-poll` kernel thread

This was triggered while the FT232H driver software-dispatched GPIO IRQs.

## IRQ Path

1. User space enables GPIO line events through gpiolib cdev.
2. gpiolib enables the mapped child IRQ (`mpsse_irq_enable_disable()`).
3. Driver polling thread (`ftdi_irq_poll_function()`) periodically reads FT232H GPIO pins.
4. On a matching condition in `ftdi_mpsse_gpio_check()`, the driver dispatches a child IRQ for that GPIO.
5. IRQ core runs `handle_simple_irq()` and eventually the consumer handler (`lineevent_irq_handler`).

Call chain from the report:

- `ftdi_irq_poll_function()`
- `generic_handle_irq()`
- `handle_simple_irq()`
- `lineevent_irq_handler()`

## Root Cause

The child IRQ was dispatched from a kthread with normal process context IRQ state.

`generic_handle_irq()` expects hardirq-like context assumptions. On modern kernels, IRQ core checks can warn if a nested IRQ handler path is entered without local IRQ state matching those expectations, which produced the warning:

- `irq ... handler ... enabled interrupts`

## Fix Applied

In `spi-ft232h.c`, direct `generic_handle_irq()` calls were replaced with a helper that wraps dispatch with:

- `local_irq_save(flags)`
- `generic_handle_irq(irq)`
- `local_irq_restore(flags)`

This ensures nested IRQ handlers execute with local IRQ state expected by IRQ core.

## Files Changed

- `spi-ft232h.c`
- `IRQ_README.md`

## Validation Steps

1. Rebuild and reload module:
   - `make`
   - `sudo rmmod spi_ft232h`
   - `sudo insmod spi-ft232h.ko`
2. Re-run your IRQ event workload.
3. Watch logs:
   - `dmesg -w`
4. Confirm the previous warning no longer appears.

## Follow-up Finding: GPIO Read Mapping Bug

After the IRQ-context fix, a second issue was identified for gpiolib GPIO reads:

- `ftdi_mpsse_gpio_get()` used a different offset/bit mapping than
  `ftdi_mpsse_gpio_set()` and direction functions.
- Specifically, read path used `offset < 5` with `BIT(offset) << 3`, while
  gpiolib write/direction path uses `offset < 4` with `BIT(offset) << 4`.

Impact:

- For `offset 4`, polling read the wrong bit/port and could appear stuck high,
  causing repeated `val 1` logs and incorrect IRQ trigger behavior.

Fix:

- Updated both GPIO helper layers to use the same mapping:
  - `ftdi_gpio_get()` / `ftdi_gpio_set()` / direction helpers
  - `ftdi_mpsse_gpio_get()` / `ftdi_mpsse_gpio_set()` / direction helpers
- Both paths now use:
  - low port when `offset < 4`
  - low bit mask `BIT(offset) << 4`
  - high bit index `BIT(offset - 4)`
- Updated IRQ polling to call `ftdi_mpsse_gpio_get()` directly so poll logic
  follows the same gpiolib mapping.

## Notes

- This driver uses GPIO polling to emulate interrupt signaling from FT232H GPIOs.
- Polling period (`irq_poll_period`) still affects latency and event burst behavior.
- If needed, further work can add edge-state tracking to reduce repeated level-trigger dispatches.
