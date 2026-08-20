module gpio (
    input  wire       clk_i,
    input  wire       rst_ni,
    output wire [7:0] gpio_o,
    input  wire [7:0] gpio_i
);
    assign gpio_o = gpio_i;
endmodule
