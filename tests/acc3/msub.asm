; Acceptance test 3, program 2: the same loop with ADC changed to SBB, as the manual says on p.6-12. The manual prints no result for it;
; the expected FIRST - SECND = 84BA90H - 32AF8AH = 520B06H comes from our own arithmetic (python), bytes 06 0B 52 at FIRST.
; Wrapper (MVI E,3, the printing, the exit) is ours; the loop is the manual p.6-12 with SBB.
        .org 0
        JMP 0x0100              ; CPU starts at 0000h; the run ends when the program jumps back here
        .org 0x0100
        MVI E,3                 ; ours: the manual says only that E holds the length
; ---- from the manual, p.6-12 -------------------------------------------------------------------
MADD:   LXI B,FIRST             ; B AND C ADDRESS FIRST
        LXI H,SECND             ; H AND L ADDRESS SECND
        XRA A                   ; CLEAR CARRY FLAG
LOOP:   LDAX B                  ; LOAD BYTE OF FIRST
        SBB M                   ; SUBTRACT BYTE OF SECND WITH BORROW (the manual: change ADC to SBB)
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
