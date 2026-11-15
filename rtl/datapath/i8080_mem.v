// Ada: 64 KiB RAM for tests. Ports and timing: docs/blocks.md (v1.1) section 2.
// rdata is combinational: it follows addr while rd = 1, else 00. A write happens on the rising clk edge with wr = 1.
// Bytes the INIT_FILE does not cover (and every byte if INIT_FILE is empty) read as 00.
module i8080_mem #(
    parameter INIT_FILE = ""
) (
    input  wire        clk,
    input  wire [15:0] addr,
    input  wire        rd,
    input  wire        wr,
    input  wire [7:0]  wdata,
    output wire [7:0]  rdata
);
    reg [7:0] mem [0:65535];
    integer i;

    initial begin
        for (i = 0; i < 65536; i = i + 1) mem[i] = 8'h00;
        if (INIT_FILE != "") $readmemh(INIT_FILE, mem);
    end

    assign rdata = rd ? mem[addr] : 8'h00;

    always @(posedge clk) begin
        if (wr) mem[addr] <= wdata;
    end
endmodule
