def register_permit_mask(msb: int, lsb: int) -> int:
    '''
    One bit presents one byte in the register, so in total 4 bits are used.
    This function check which byte the register field is in and return the mask.
    The caller should loop the register fields and OR the values returned by this
    function the get the final permit representation for a register.
    '''
    mask = 0
    for bit in range(lsb, msb+1):
        byte_index = bit // 8
        mask |= (1 << byte_index)
    return mask

def needs_read_en(reg: dict()) -> bool:                                                          
     '''Return true if at least one field needs a read-enable                         
                                                                                      
     This is true if any of the following are true:                                   
                                                                                      
       - The register is shadowed, because the read has a side effect.                
         I.e., this puts the register back into Phase 0 (next write will              
         go to the staged register). This is useful for software in case              
         it lost track of the current phase. See comportability spec for              
         more details:                                                                
         https://docs.opentitan.org/doc/rm/register_tool/#shadow-registers            
                                                                                      
       - There's an RC field (where we'll attach the read-enable signal to            
         the subreg's we port)                                                        
                                                                                      
       - The register is hwext and allows reads (in which case the hardware           
         side might need the re signal)                                               
     '''                                                                              
     return reg['shadowed'] or any([(field['clear_onread'] or (reg['external'] and field['sw_readable'])) for field in reg['fields']])
                                                                                      

def needs_write_en(reg: dict()) -> bool:                                                          
    '''Should the register for this field have a write-enable signal?

        This is almost the same as allows_write(), but doesn't return true for
        RC registers, which should use a read-enable signal (connected to their
        prim_subreg's we port).
     '''
    return any([(not field['clear_onread'] and field['sw_writable']) for field in reg['fields']])                                                          

def needs_qe(reg: dict()) -> bool:
    '''Return true if the register or at least one field needs a q-enable'''
    return any( [field['swmod'] for field in reg['fields']] )

def needs_int_qe(reg: dict()) -> bool:
    '''Return true if the register or at least one field needs an
       internal q-enable.  An internal q-enable means the net
       may be consumed by other reg logic but will not be exposed
       in the package file.'''
    return (reg['async'] and reg['hw_writable']) or needs_qe(reg) 

def get_bit_width(offset: int) -> int:
    '''Calculate the number of bits to address every byte of the block'''
    return (offset - 1).bit_length()

