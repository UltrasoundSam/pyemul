value = $2000 ; two bytes
mod10 = $2002 ; two bytes

  .org $8000
reset:
  ; Initialise value from number in ROM
  lda number  
  sta value
  lda number + 1
  sta value + 1
  
  ; Initialise mod10 to zero
  lda #0 
  sta mod10
  sta mod10 + 1
  clc
  
  ldx #16  
divloop:
  ; Rotate left
  rol value
  rol value + 1
  rol mod10
  rol mod10 + 1
  
  ; a,y = divident - divisor
  sec
  lda mod10
  sbc #10
  tay ; save low byte in Y
  lda mod10 + 1
  sbc #0
  bcc ignore_result ; branch is divident < divisor
  sty mod10
  sta mod10 + 1
  
ignore_result:
  dex
  bne divloop
  rol value
  rol value + 1 

loop:
  jmp loop  
 
number: .word 16320
divisor: .byte 5

  .org $fffc
  .word reset
  .word $0000