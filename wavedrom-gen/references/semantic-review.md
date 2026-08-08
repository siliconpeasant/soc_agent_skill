# Timing semantic review

Use this checklist after rendering implementation-accurate diagrams.

## Clocking and causality

- Assign every synchronous signal to a clock domain and active edge.
- Place clock-domain boundaries explicitly; split the diagram if separate time bases would be misleading.
- Confirm that each synchronous transition has a causal clock edge.
- Show registered outputs after the edge that captures their inputs; do not insert an extra cycle into combinational behavior.
- Treat asynchronous resets, CDC inputs, and external events as explicit exceptions.

## Handshakes and buses

- Mark the transfer on the active edge where the handshake condition is true.
- Hold payload stable through backpressure when the protocol requires it.
- Align multi-bit values with their valid, enable, select, or direction qualifier.
- Distinguish a new data value from a held value and from an unknown value.
- Preserve specified active-low naming and polarity.

## Protocol fidelity

- Check CPOL/CPHA, sample edge, shift edge, bit order, and chip-select boundaries for SPI.
- Check start/stop conditions, SDA stability while SCL is high, bit order, and ACK ownership for I2C.
- Check idle, start, data order, parity, stop, and sample position for UART.
- Check reset polarity, synchronous/asynchronous behavior, and post-reset values.

## Visual truthfulness

- Make the diagram's time unit and any compression visible.
- Do not use arrows to imply an unverified propagation or setup/hold value.
- Do not hide a specification/implementation mismatch by adjusting `phase` for appearance.
- Split dense diagrams instead of shrinking labels until they are unreadable.
- List every assumption that a reviewer would need to distinguish fact from illustration.
