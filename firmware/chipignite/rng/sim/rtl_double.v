// SPDX-FileCopyrightText: 2020 Efabless Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// SPDX-License-Identifier: Apache-2.0

`default_nettype none
/*
 *-------------------------------------------------------------
 *
 * user_proj_example
 *
 * This is an example of a (trivially simple) user project,
 * showing how the user project can connect to the logic
 * analyzer, the wishbone bus, and the I/O pads.
 *
 * This project generates an integer count, which is output
 * on the user area GPIO pads (digital output only).  The
 * wishbone connection allows the project to be controlled
 * (start and stop) from the management SoC program.
 *
 * See the testbenches in directory "mprj_counter" for the
 * example programs that drive this user project.  The three
 * testbenches are "io_ports", "la_test1", and "la_test2".
 *
 *-------------------------------------------------------------
 */

module user_proj_example #(
    parameter BITS = 32
)(
`ifdef USE_POWER_PINS
    inout vccd1,	// User area 1 1.8V supply
    inout vssd1,	// User area 1 digital ground
`endif

    // Wishbone Slave ports (WB MI A)
    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output reg wbs_ack_o,
    output reg [31:0] wbs_dat_o,

    // Logic Analyzer Signals
    input  [127:0] la_data_in,
    output [127:0] la_data_out,
    input  [127:0] la_oenb,

    // IOs
    input  [`MPRJ_IO_PADS-1:0] io_in,
    output [`MPRJ_IO_PADS-1:0] io_out,
    output [`MPRJ_IO_PADS-1:0] io_oeb,

    // IRQ
    output [2:0] irq
);

localparam [31:0] X_INIT = 32'hDE78D681;
localparam [31:0] Y_INIT = 32'hFEEE4640;
localparam [31:0] Z_INIT = 32'hFE8E511B;

    wire clk;
    wire rst;

	wire [31:0]x;
	wire [31:0]y;
	wire [31:0]z;
	
	reg [31:0]x_init, x_data;
	reg [31:0]y_init, y_data;
	reg [31:0]z_init, z_data;
	
	reg [23:0]set_scroll_num;
	reg [3:0]rng_en;
	reg smp_en;

    //WRITE REGS WITH WISHBONE
	always @(posedge wb_clk_i) begin 
		if (wb_rst_i) begin
			x_init <= X_INIT;
			y_init <= Y_INIT;
			z_init <= Z_INIT;
			set_scroll_num <= {8'h4d, 8'h4c, 8'h4b};
			rng_en <= 4'h3;
			smp_en <= 1'b0;
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h04)begin
			x_init <= wbs_dat_i;
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h08)begin
			y_init <= wbs_dat_i;
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h0c)begin
			z_init <= wbs_dat_i;
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h10)begin
			set_scroll_num <= wbs_dat_i[23:0];
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h14)begin
			rng_en <= wbs_dat_i[3:0];
		end else if (wbs_stb_i && wbs_cyc_i && wbs_we_i && wbs_adr_i[7:0] == 8'h18)begin
			smp_en <= wbs_dat_i[0];
		end else begin
			smp_en <= 1'b0;
		end
	end
	
	//READ REGS WITH WISHBONE
	always @(posedge wb_clk_i) begin 
		if (wb_rst_i) begin
			wbs_dat_o <= 32'h0;
		end else if(wbs_stb_i && wbs_cyc_i && !wbs_we_i) begin
			case(wbs_adr_i[7:0])
				8'h04	: wbs_dat_o <= x_init;
				8'h08	: wbs_dat_o <= y_init;
				8'h0c	: wbs_dat_o <= z_init;
				8'h10	: wbs_dat_o <= {8'h0, set_scroll_num};
				8'h14	: wbs_dat_o <= {28'h0, rng_en};
				8'h18	: wbs_dat_o <= smp_en;
				8'h1c	: wbs_dat_o <= x_data;
				8'h20	: wbs_dat_o <= y_data;
				8'h24	: wbs_dat_o <= z_data;
				default	: wbs_dat_o <= 32'h0;
			endcase
		end
	end
	
	// ACK WISHBONE
	always @(posedge wb_clk_i) begin 
		if (wb_rst_i) begin
			wbs_ack_o <= 1'b0;
		end else begin
			wbs_ack_o <= (wbs_stb_i && wbs_cyc_i);
		end
	end
	
	// SMP XYZ 
	always @(posedge wb_clk_i) begin 
		if (wb_rst_i) begin
			x_data <= 32'h0;
			y_data <= 32'h0;
			z_data <= 32'h0;
		end else if (smp_en) begin
		    x_data <= x;
			y_data <= y;
			z_data <= z;
		end
	end


    // IO
    assign io_out = x;
    assign io_oeb = {(`MPRJ_IO_PADS-1){1'b1}};

    // IRQ
    assign irq = 3'b000;	// Unused

    // LA
    assign la_data_out = {{32{1'b0}}, z, y, x};
	
    // Assuming LA probes [97:96] are for controlling the count clk & reset  
    assign clk = (~la_oenb[96]) ? la_data_in[96]: wb_clk_i;
    assign rst = (~la_oenb[97]) ? la_data_in[97]: wb_rst_i;

    rng_chaos_scroll u_rng_chaos_chaos (
        .clk(clk),
        .rst(rst),
        .en(rng_en),
		.x_init(x_init),
		.y_init(y_init),
		.z_init(z_init),
		.Lx(set_scroll_num[3:0]),
		.Ux(set_scroll_num[6:4]),
		.Ly(set_scroll_num[11:8]),
		.Uy(set_scroll_num[14:12]),
		.Lz(set_scroll_num[19:16]),
		.Uz(set_scroll_num[22:20]),
		.x(x),
		.y(y),
		.z(z)
    );

endmodule

module rng_chaos_scroll(
	input clk, 
	input rst, 
	input [ 3:0] en, 
	input [31:0] x_init, 
	input [31:0] y_init, 
	input [31:0] z_init,
	input [ 3:0] Lx,                                                            
	input [ 2:0] Ux,
	input [ 3:0] Ly,                                                            
	input [ 2:0] Uy,	
	input [ 3:0] Lz,                                                            
	input [ 2:0] Uz,	
	output reg [31:0] x, 
	output reg [31:0] y, 
	output reg [31:0] z
);

// wires                                                                   
wire [31:0] Fx, xn, xo;                                                       
wire [31:0] Fy, yn, yo;                                                       
wire [31:0] Fz, zn, zo, zd, zd1, zd2;                                                                                                           

assign Lx = 4'b1011;                                                      
assign Ux = 3'b100;

func Fx_func(                                                     
    .F_i(x),                                                               
    .U_i(Ux),                                                              
    .L_i(Lx),                                                              
    .F_o(Fx)                                                               
    );                                                                            

assign xo = en[1] ? Fx : x;

func Fy_func(                                                     
    .F_i(y),                                                               
    .U_i(Uy),                                                              
    .L_i(Ly),                                                              
    .F_o(Fy)                                                               
    ); 
	
assign yo = en[2] ? Fy : y;
	
func Fz_func(                                                     
    .F_i(z),                                                               
    .U_i(Uz),                                                              
    .L_i(Lz),                                                              
    .F_o(Fz)                                                               
    ); 

assign zo = en[3] ? Fz : z;

assign zd1 = xo+yo+zo;
assign zd2 = {{4{ zd1[31]}},  zd1[31:4]};                        
assign zd =   zd1 - zd2;

assign xn = x + {{3{yo[31]}}, yo[31:3]};
assign yn = y + {{3{zo[31]}}, zo[31:3]};
assign zn = z - {{3{zd[31]}}, zd[31:3]}; 

always @(posedge clk)                                                    
begin                                                                      
	if(rst) begin                                                      
        x <= x_init;                                                          
        y <= y_init;                                                         
        z <= z_init;                                                          
	end else if (en[0]) begin                                                            
		x <= xn;                                                                 
		y <= yn;                                                                 
		z <= zn;                                                             
	end	                                                                      
end

endmodule

module func(
    input   [31:0] F_i,
    input   [ 2:0] U_i,
    input   [ 3:0] L_i,
    output  [31:0] F_o
    );   
 
 wire [ 5:0] Xhigh;
 wire [ 5:0] X26_6n;
 wire [ 5:0] Se_U;
 wire [ 5:0] XU;
 wire [ 5:0] XU_X26;
 wire [ 5:0] out_6b;

  assign Xhigh  = F_i[31:26] - {L_i[3],L_i,1'b1};
  assign X26_6n = ~{6{F_i[26]}};
  assign Se_U   = {U_i[2],U_i[2],U_i,1'b1};
  assign XU     = F_i[31:26] - Se_U;
  assign XU_X26 = (XU[5]) ? X26_6n : XU;
  assign out_6b = (Xhigh[5]) ?  Xhigh : XU_X26;
  assign F_o = {out_6b, F_i[25:0]};

endmodule

`default_nettype wire
