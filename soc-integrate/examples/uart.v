module uart (
    input  wire        clk_i,
    input  wire        rst_ni,
    output wire        tx_o,
    input  wire        rx_i
);
    assign tx_o = rx_i;
endmodule
