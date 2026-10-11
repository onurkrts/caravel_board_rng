`timescale 1ns/1ps
`define MPRJ_IO_PADS 38
module tb;
  reg clk = 0;
  reg [127:0] la_in = 0, la_oenb = {128{1'b1}};
  wire [127:0] la_out;
  wire [37:0] io_out, io_oeb;
  wire [31:0] dato;
  wire ack;
  wire [2:0] irq;
  integer i, f;

  user_proj_example dut(
    .wb_clk_i(clk), .wb_rst_i(1'b0), .wbs_stb_i(1'b0), .wbs_cyc_i(1'b0), .wbs_we_i(1'b0),
    .wbs_sel_i(4'h0), .wbs_dat_i(32'h0), .wbs_adr_i(32'h0), .wbs_ack_o(ack), .wbs_dat_o(dato),
    .la_data_in(la_in), .la_data_out(la_out), .la_oenb(la_oenb),
    .io_in(38'b0), .io_out(io_out), .io_oeb(io_oeb), .irq(irq));

  always #5 clk = ~clk;

  initial begin
    la_oenb[96] = 0; la_oenb[97] = 0;
    la_in[97] = 0; la_in[96] = 0;
    #20 la_in[96] = 1; #20 la_in[96] = 0;
    #20 la_in[97] = 1;
    f = $fopen("rtl_single.txt", "w");
    for (i = 0; i < 200000; i = i + 1) begin
      $fwrite(f, "%08x %08x %08x\n", la_out[31:0], la_out[63:32], la_out[95:64]);
      #10 la_in[96] = 1; #10 la_in[96] = 0;
    end
    $fclose(f);
    $finish;
  end
endmodule
