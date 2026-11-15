; Acceptance test 3, program 4 (spec section 9 item 3): the decimal subtraction routine DSUB from the Intel 8080/8085
; Assembly Language Programming Manual, p.6-17 (listing checked against the page image), run on the manual's worked example
; of pp.6-14 to 6-16: 4358 - 1362 = 2996.
; From the manual: the numbers are 16 decimal digits, two per byte, least significant byte first, the result replaces the
; minuend. The worked example's bytes are 58H, 43H (minuend 4358) and 62H, 13H (subtrahend 1362), and the manual prints the
; result bytes 96H then 29H, with the accumulator values 9AH, 38H, 90H, 96H (carry 0) and 99H, 86H, C9H, 29H (carry 1).
; Ours: the remaining six bytes of each number are 00 (so the manual's result bytes are followed by six 00 bytes: our
; arithmetic, no borrow), SP, the data, and the printing of all eight result bytes, then the jump to 0000h.
; Expected output: 9629000000000000
        .org 0
        JMP 0x0100
        .org 0x0100
        LXI SP,0xFFF0           ; ours
; ---- from the manual, p.6-17 ----------------------------------------------------------------------
DSUB:   LXI D,MINU              ; D AND E ADDRESS MINUEND
        LXI H,SBTRA             ; H AND L ADDRESS SUBTRAHEND
        MVI C,8                 ; EACH LOOP SUBTRACTS 2 DIGITS (ONE BYTE), THEREFORE PROGRAM WILL SUBTRACT 16 DIGITS
        STC                     ; SET CARRY INDICATING NO BORROW
LOOP:   MVI A,0x99              ; LOAD ACCUMULATOR WITH 99H (the manual writes 99H; our assembler wants 0x99)
        ACI 0                   ; ADD ZERO WITH CARRY
        SUB M                   ; PRODUCE COMPLEMENT OF SUBTRAHEND
        XCHG                    ; SWITCH D AND E WITH H AND L
        ADD M                   ; ADD MINUEND
        DAA                     ; DECIMAL ADJUST ACCUMULATOR
        MOV M,A                 ; STORE RESULT
        XCHG                    ; RESWITCH D AND E WITH H AND L
        DCR C                   ; DONE IF C = 0
        JZ DONE
        INX D                   ; ADDRESS NEXT BYTE OF MINUEND
        INX H                   ; ADDRESS NEXT BYTE OF SUBTRAHEND
        JMP LOOP                ; GET NEXT 2 DECIMAL DIGITS
; ---- ours: print the eight result bytes (least significant first) as hex through the BDOS port, then end ---------
DONE:   LXI H,MINU
        MVI B,8
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
MINU:   .byte 0x58, 0x43, 0, 0, 0, 0, 0, 0      ; 4358, the manual's worked example (the six zero bytes are ours)
SBTRA:  .byte 0x62, 0x13, 0, 0, 0, 0, 0, 0      ; 1362
