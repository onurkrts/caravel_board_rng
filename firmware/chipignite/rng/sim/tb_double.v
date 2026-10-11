`timescale 1ns/1ps
`define MPRJ_IO_PADS 38
module tb;
  reg clk = 0, wb_rst = 1;
  reg stb = 0, cyc = 0, we = 0;
  reg [31:0] adr = 0, dat = 0;
  reg [127:0] la_in = 0, la_oenb = {128{1'b1}};
  wire ack;
  wire [31:0] dato;
  wire [127:0] la_out;
  wire [37:0] io_out, io_oeb;
  wire [2:0] irq;
  integer i, f;

  user_proj_example dut(
    .wb_clk_i(clk), .wb_rst_i(wb_rst), .wbs_stb_i(stb), .wbs_cyc_i(cyc), .wbs_we_i(we),
    .wbs_sel_i(4'hf), .wbs_dat_i(dat), .wbs_adr_i(adr), .wbs_ack_o(ack), .wbs_dat_o(dato),
    .la_data_in(la_in), .la_data_out(la_out), .la_oenb(la_oenb),
    .io_in(38'b0), .io_out(io_out), .io_oeb(io_oeb), .irq(irq));

  always #5 clk = ~clk;

  task wb_read(input [31:0] a);
    begin
      @(negedge clk); adr = a; stb = 1; cyc = 1; we = 0;
      @(posedge clk); while (!ack) @(posedge clk);
      #1 $display("WB read  %h = %h", a, dato);
      @(negedge clk); stb = 0; cyc = 0;
    end
  endtask

  task wb_write(input [31:0] a, input [31:0] d);
    begin
      @(negedge clk); adr = a; dat = d; stb = 1; cyc = 1; we = 1;
      @(posedge clk); while (!ack) @(posedge clk);
      @(negedge clk); stb = 0; cyc = 0; we = 0;
    end
  endtask

  initial begin
    repeat (3) @(posedge clk);
    #1 wb_rst = 0;
    wb_read(32'h30000004); wb_read(32'h30000008); wb_read(32'h3000000c);
    wb_read(32'h30000010); wb_read(32'h30000014);
    la_oenb[96] = 0; la_oenb[97] = 0;
    la_in[97] = 1; la_in[96] = 0;
    #20 la_in[96] = 1; #20 la_in[96] = 0;
    #20 la_in[97] = 0;
    f = $fopen("rtl_double.txt", "w");
    for (i = 0; i < 200000; i = i + 1) begin
      $fwrite(f, "%08x %08x %08x\n", la_out[31:0], la_out[63:32], la_out[95:64]);
      #10 la_in[96] = 1; #10 la_in[96] = 0;
    end
    $fclose(f);
    wb_write(32'h30000018, 1);
    wb_read(32'h3000001c); wb_read(32'h30000020); wb_read(32'h30000024);
    $display("LA       %h %h %h", la_out[31:0], la_out[63:32], la_out[95:64]);
    $finish;
  end
endmodule
