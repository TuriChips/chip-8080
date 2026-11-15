; Acceptance test 3, program 5 (spec section 9 item 3): decimal addition from the Intel 8080/8085 Assembly Language
; Programming Manual, pp.6-12 to 6-14. The manual's routine is one sentence: MADD (p.6-12) "with the instruction DAA inserted
; after the ADC M instruction". So the program is the manual's MADD loop with DAA after ADC M, run on the manual's worked
; example 2985 + 4936 = 7921 (p.6-13: 85H + 36H = 0BBH, DAA gives 21H with carry 1; 29H + 49H + carry = 73H, DAA gives 79H).
; From the manual: the digits as bytes, least significant first: FIRST = 85H, 29H and SECND = 36H, 49H; the result bytes 21H, 79H.
; Ours: the wrapper (E = 2, SP, the printing, the exit). The DAA insertion is the manual's stated change, but where the
; manual does not list the code the placement is our reading of "after ADC M".
; Expected output: 2179
        .org 0
        JMP 0x0100
        .org 0x0100
        LXI SP,0xFFF0           ; ours
        MVI E,2                 ; ours: two bytes = four digits
; ---- MADD from the manual (p.6-12) with DAA inserted after ADC M (p.6-14) -----------------------------
MADD:   LXI B,FIRST             ; B AND C ADDRESS FIRST
        LXI H,SECND             ; H AND L ADDRESS SECND
        XRA A                   ; CLEAR CARRY FLAG
LOOP:   LDAX B                  ; LOAD BYTE OF FIRST
        ADC M                   ; ADD BYTE OF SECND WITH CARRY
        DAA                     ; the manual's insertion: decimal adjust before the next byte
        STAX B                  ; STORE RESULT AT FIRST
        DCR E                   ; DONE IF E = 0
        JZ DONE
        INX B                   ; POINT TO NEXT BYTE OF FIRST
        INX H                   ; POINT TO NEXT BYTE OF SECND
        JMP LOOP                ; ADD NEXT TWO BYTES
; ---- ours: print the result bytes as hex through the BDOS port, then end -----------------------------
DONE:   LXI H,FIRST
        MVI B,2
PRT:    MOV A,M
        CALL PBYTE
        INX H
        DCR B
        JNZ PRT
        MVI A,10
        OUT 0
        JMP 0x0000
PBYTE:  PUSH PSW
        RRC
        RRC
        RRC
        RRC
        CALL NIB
        POP PSW
NIB:    ANI 0x0F
        ADI 0x30
        CPI 0x3A
        JC OUTC
        ADI 7
OUTC:   OUT 0
        RET
FIRST:  .byte 0x85, 0x29        ; 2985
SECND:  .byte 0x36, 0x49        ; 4936
