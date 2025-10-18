//! Bitset utilities for representing Konkan card sets.

pub fn card_bitmask(card_id: u8) -> u128 {
    1u128 << card_id
}

pub fn combine_mask(mask: u128) -> (u64, u64) {
    (
        ((mask >> 64) & ((1u128 << 64) - 1)) as u64,
        (mask & ((1u128 << 64) - 1)) as u64,
    )
}

pub fn merge_words(mask_hi: u64, mask_lo: u64) -> u128 {
    ((mask_hi as u128) << 64) | mask_lo as u128
}
