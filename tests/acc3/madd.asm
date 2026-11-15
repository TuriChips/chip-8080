; Acceptance test 3, program 1 (spec section 9 item 3): the multibyte addition routine MADD from the Intel
; 8080/8085 Assembly Language Programming Manual, p.6-12 (listing and data), with our own wrapper that prints the result.
; Manual's data: FIRST = 90H, 0BAH, 84H and SECND = 8AH, 0AFH, 32H, E = 3. Manual's result: bytes 1A 6A B7 at FIRST ("1A6AB7").
; (The figure on p.6-11 swaps which number is FIRST; the sum is the same.)
        .org 0
        JMP 0x0100              ; CPU starts at 0000h; the run ends when the program jumps back here
        .org 0x0100
        MVI E,3                 ; ours: the manual says only that E holds the length
; ---- from the manual, p.6-12 -------------------------------------------------------------------
MADD:   LXI B,FIRST             ; B AND C ADDRESS FIRST
        LXI H,SECND             ; H AND L ADDRESS SECND
        XRA A                   ; CLEAR CARRY FLAG
LOOP:   LDAX B                  ; LOAD BYTE OF FIRST
        ADC M                   ; ADD BYTE OF SECND WITH CARRY
        STAX B                  ; STORE RESULT AT FIRST
        DCR E                   ; DONE IF E = 0
        JZ DONE
        INX B                   ; POINT TO NEXT BYTE OF FIRST
        INX H                   ; POINT TO NEXT BYTE OF SECND
        JMP LOOP                ; ADD NEXT TWO BYTES
; ---- ours: print the three result bytes as hex through the BDOS port (OUT 0), then end ------------
DONE:   LXI H,FIRST
        MVI B,3
PRT:    MOV A,M
        PUSH PSW
        RRC
        RRC
        RRC
        RRC
        CALL NIB
        POP PSW
        CALL NIB
        INX H
        DCR B
        JNZ PRT
        MVI A,10
        OUT 0
        JMP 0x0000
NIB:    ANI 0x0F
        ADI 0x30
        CPI 0x3A
        JC OUTC
        ADI 7
OUTC:   OUT 0
        RET
FIRST:  .byte 0x90, 0xBA, 0x84
SECND:  .byte 0x8A, 0xAF, 0x32
