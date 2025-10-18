//! Card metadata and helpers for the Konkan meld solver.

pub const NUM_RANKS: usize = 13;
pub const NUM_SUITS: usize = 4;
pub const JOKER_IDS: [u8; 2] = [104, 105];
pub const KIND_SET: u8 = 0;
pub const KIND_RUN: u8 = 1;

const RANK_POINTS: [i32; NUM_RANKS] = [10, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10];

#[derive(Clone, Copy)]
pub struct CardInfo {
    pub id: u8,
    pub rank: Option<u8>,
    pub suit: Option<u8>,
}

pub fn decode_card(id: u8) -> CardInfo {
    if id >= JOKER_IDS[0] {
        return CardInfo {
            id,
            rank: None,
            suit: None,
        };
    }
    let copy = id / 52;
    let base = id - copy * 52;
    let suit = base / 13;
    let rank = base % 13;
    CardInfo {
        id,
        rank: Some(rank),
        suit: Some(suit),
    }
}

pub fn points_for_rank(rank: u8) -> i32 {
    RANK_POINTS[rank as usize]
}

pub fn collect_cards(mask_hi: u64, mask_lo: u64) -> (Vec<CardInfo>, Vec<u8>) {
    let mut cards = Vec::new();
    let mut jokers = Vec::new();
    for id in 0..=105 {
        let bit_present = if id < 64 {
            (mask_lo >> id) & 1 == 1
        } else {
            let offset = id - 64;
            if offset >= 64 {
                false
            } else {
                (mask_hi >> offset) & 1 == 1
            }
        };
        if !bit_present {
            continue;
        }
        if id >= JOKER_IDS[0] as usize {
            jokers.push(id as u8);
        } else {
            cards.push(decode_card(id as u8));
        }
    }
    (cards, jokers)
}
