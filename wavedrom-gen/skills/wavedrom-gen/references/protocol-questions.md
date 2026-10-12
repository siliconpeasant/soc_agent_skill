# Protocol clarification and defaults

Read only the section relevant to the user's request. Explicit user facts override every default below.

## General questions

Determine the diagram's purpose, time unit, clock domain, active edge, initial/final state, active-low signals, values to label, and whether the result must match an implementation. Ask only about missing facts that change the intended diagram.

For a conceptual draft, keep the transaction short and disclose assumptions. For implementation-accurate work, do not substitute defaults for unspecified protocol parameters.

## SPI

Potentially material parameters:

- CPOL and CPHA or SPI mode;
- word width and bit order;
- controller/peripheral direction and whether MOSI, MISO, or both carry data;
- chip-select polarity and behavior between words;
- transmitted values and number of words.

Conceptual default when permitted: mode 0, active-low chip select, MSB first, one 8-bit word. Label it as an assumption.

## I2C

Potentially material parameters:

- start, repeated-start, and stop sequence;
- 7-bit or 10-bit address and R/W direction;
- address and data values;
- ACK/NACK ownership and position;
- number of bytes.

Represent the defined SCL/SDA levels and bit slots. Do not expand an entire transaction when the user only wants a start, ACK, or repeated-start relationship.

## UART

Potentially material parameters:

- data-bit count;
- parity mode;
- stop-bit count;
- transmitted value;
- oversampling or receiver sample point when relevant.

Conventional framing is idle high, start low, LSB first. Use those conventions only for a conceptual draft or when the user confirms them.

## AXI-style valid/ready

Identify the channel, clock, reset behavior, payload signals, backpressure duration, and the exact transfer cycle. A transfer occurs on the active clock edge where both `valid` and `ready` are asserted. Hold payload stable while `valid` is asserted and `ready` is deasserted unless the governing specification says otherwise.

## Request/acknowledge

Clarify whether signals are pulses or levels, whether the handshake is synchronous, expected response latency, deassertion ordering, and whether overlapping transactions are allowed. Do not imply a one-cycle response unless specified or explicitly assumed.

## Reset and initialization

Clarify synchronous versus asynchronous reset, polarity, assertion/deassertion edge, minimum duration, and post-reset values. Mark signals unknown only when their values are genuinely unspecified.

## PWM, GPIO, and enables

For PWM, identify period, duty cycle, polarity, and number of periods. For GPIO or enables, identify active level, trigger event, pulse width, and clock relationship. Do not add bus-oriented labels to scalar signals.
