; Demo for the 8080 (Homer, our own program): adds 1 + 2 + ... + 100 in a 16-bit register pair with a loop, prints the sum
; in decimal through the BDOS console (OUT 0), and ends by jumping to 0000h.
; Expected console output (sw/demo.expected): "8080: 1+2+...+100 = 5050"
        .org 0
        JMP 0x0100
        .org 0x0100
        LXI SP,0xFFF0
        LXI D,MSG
        CALL PSTR               ; the text before the number
        LXI H,0                 ; HL = sum
        MVI B,100               ; B = counter, adds 100 down to 1
        MVI D,0                 ; D stays 0: DE = 0B
LOOP:   MOV E,B                 ; DE = B
        DAD D                   ; HL = HL + DE
        DCR B
        JNZ LOOP                ; ... until B = 0
        CALL PDEC               ; print HL in decimal
        MVI A,10
        OUT 0
        JMP 0x0000
; print the text at DE up to a 0 byte
PSTR:   LDAX D
        ORA A
        RZ
        OUT 0
        INX D
        JMP PSTR
; print HL as an unsigned decimal number without leading zeros: subtract 10000, 1000, 100, 10, 1 as often as it fits
PDEC:   LXI B,10000
        CALL DIGIT
        LXI B,1000
        CALL DIGIT
        LXI B,100
        CALL DIGIT
        LXI B,10
        CALL DIGIT
        MOV A,L
        ADI 0x30
        OUT 0                   ; the last digit is always printed
        RET
; one decimal digit: count how many times BC fits into HL; skip the digit if it is a leading zero
DIGIT:  MVI D,0                 ; D = digit
DLOOP:  MOV A,L
        SUB C
        MOV E,A                 ; E = low byte of HL - BC
        MOV A,H
        SBB B                   ; A = high byte of HL - BC; carry set if HL < BC
        JC DSHOW
        MOV H,A
        MOV L,E
        INR D
        JMP DLOOP
DSHOW:  MOV A,D
        ORA A
        JNZ DOUT
        LDA SEEN
        ORA A
        RZ                      ; leading zero: print nothing
DOUT:   MVI A,1
        STA SEEN
        MOV A,D
        ADI 0x30
        OUT 0
        RET
SEEN:   .byte 0
MSG:    .byte 0x38, 0x30, 0x38, 0x30, 0x3A, 0x20            ; "8080: "
        .byte 0x31, 0x2B, 0x32, 0x2B, 0x2E, 0x2E, 0x2E, 0x2B  ; "1+2+...+"
        .byte 0x31, 0x30, 0x30, 0x20, 0x3D, 0x20, 0           ; "100 = "
