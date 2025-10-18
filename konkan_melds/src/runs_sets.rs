//! Enumeration of Konkan meld candidates (runs and sets).

use std::collections::HashSet;

use crate::bitset::{card_bitmask, combine_mask};
use crate::deck::{
    collect_cards, decode_card, points_for_rank, CardInfo, KIND_RUN, KIND_SET, NUM_RANKS, NUM_SUITS,
};
use crate::Meld;

fn cartesian_product(lists: &[&[u8]]) -> Vec<Vec<u8>> {
    if lists.is_empty() {
        return vec![Vec::new()];
    }
    let mut results = Vec::new();
    let mut current = Vec::with_capacity(lists.len());
    fn recurse(
        lists: &[&[u8]],
        index: usize,
        current: &mut Vec<u8>,
        results: &mut Vec<Vec<u8>>,
    ) {
        if index == lists.len() {
            results.push(current.clone());
            return;
        }
        for &value in lists[index] {
            current.push(value);
            recurse(lists, index + 1, current, results);
            current.pop();
        }
    }
    recurse(lists, 0, &mut current, &mut results);
    results
}

fn joker_combinations(jokers: &[u8], k: usize) -> Vec<Vec<u8>> {
    if k == 0 {
        return vec![Vec::new()];
    }
    if jokers.len() < k {
        return Vec::new();
    }
    let mut results = Vec::new();
    let mut current = Vec::with_capacity(k);
    fn recurse(
        jokers: &[u8],
        start: usize,
        k: usize,
        current: &mut Vec<u8>,
        results: &mut Vec<Vec<u8>>,
    ) {
        if current.len() == k {
            results.push(current.clone());
            return;
        }
        for idx in start..jokers.len() {
            current.push(jokers[idx]);
            recurse(jokers, idx + 1, k, current, results);
            current.pop();
        }
    }
    recurse(jokers, 0, k, &mut current, &mut results);
    results
}

fn enumerate_sets(cards: &[CardInfo], jokers: &[u8]) -> Vec<Meld> {
    let mut by_rank = vec![vec![Vec::<u8>::new(); NUM_SUITS]; NUM_RANKS];
    for card in cards {
        if let (Some(rank), Some(suit)) = (card.rank, card.suit) {
            by_rank[rank as usize][suit as usize].push(card.id);
        }
    }

    let mut results = Vec::new();
    let mut seen_masks: HashSet<u128> = HashSet::new();
    let max_jokers = jokers.len();

    for rank in 0..NUM_RANKS {
        let suit_lists = &by_rank[rank];
        for target_size in 3..=4 {
            for subset_mask in 1usize..(1 << NUM_SUITS) {
                let actual_count = subset_mask.count_ones() as usize;
                if actual_count == 0 || actual_count > target_size {
                    continue;
                }
                let mut lists: Vec<&[u8]> = Vec::with_capacity(actual_count);
                let mut valid = true;
                for suit in 0..NUM_SUITS {
                    if (subset_mask & (1 << suit)) == 0 {
                        continue;
                    }
                    if suit_lists[suit].is_empty() {
                        valid = false;
                        break;
                    }
                    lists.push(suit_lists[suit].as_slice());
                }
                if !valid {
                    continue;
                }
                let jokers_needed = target_size - actual_count;
                if jokers_needed > max_jokers {
                    continue;
                }

                let actual_combos = cartesian_product(&lists);
                let joker_combos = joker_combinations(jokers, jokers_needed);

                for actual_cards in &actual_combos {
                    for joker_cards in &joker_combos {
                        let mut mask: u128 = 0;
                        for &card_id in actual_cards {
                            mask |= card_bitmask(card_id);
                        }
                        for &joker_id in joker_cards {
                            mask |= card_bitmask(joker_id);
                        }
                        if seen_masks.insert(mask) {
                            let (mask_hi, mask_lo) = combine_mask(mask);
                            let points = points_for_rank(rank as u8) * target_size as i32;
                            results.push(Meld {
                                mask_hi,
                                mask_lo,
                                points,
                                jokers_used: jokers_needed as u8,
                                kind: KIND_SET,
                            });
                        }
                    }
                }
            }
        }
    }

    results
}

fn explore_run(
    rank_lists: &[Vec<u8>],
    current_rank: usize,
    current_cards: &mut Vec<u8>,
    seen_masks: &mut HashSet<u128>,
    results: &mut Vec<Meld>,
) {
    if current_rank >= NUM_RANKS {
        return;
    }
    let cards = &rank_lists[current_rank];
    if cards.is_empty() {
        return;
    }
    for &card_id in cards {
        current_cards.push(card_id);
        if current_cards.len() >= 3 {
            let mut mask: u128 = 0;
            let mut points: i32 = 0;
            for &cid in current_cards.iter() {
                mask |= card_bitmask(cid);
                let info = decode_card(cid);
                if let Some(rank) = info.rank {
                    points += points_for_rank(rank);
                }
            }
            if seen_masks.insert(mask) {
                let (mask_hi, mask_lo) = combine_mask(mask);
                results.push(Meld {
                    mask_hi,
                    mask_lo,
                    points,
                    jokers_used: 0,
                    kind: KIND_RUN,
                });
            }
        }
        if current_rank + 1 < NUM_RANKS && !rank_lists[current_rank + 1].is_empty() {
            explore_run(
                rank_lists,
                current_rank + 1,
                current_cards,
                seen_masks,
                results,
            );
        }
        current_cards.pop();
    }
}

fn enumerate_runs(cards: &[CardInfo]) -> Vec<Meld> {
    let mut per_suit = vec![vec![Vec::<u8>::new(); NUM_RANKS]; NUM_SUITS];
    for card in cards {
        if let (Some(rank), Some(suit)) = (card.rank, card.suit) {
            per_suit[suit as usize][rank as usize].push(card.id);
        }
    }

    let mut results = Vec::new();
    let mut seen_masks: HashSet<u128> = HashSet::new();
    for suit in 0..NUM_SUITS {
        let rank_lists = &per_suit[suit];
        for start in 0..NUM_RANKS {
            if rank_lists[start].is_empty() {
                continue;
            }
            let mut current_cards = Vec::new();
            explore_run(
                rank_lists,
                start,
                &mut current_cards,
                &mut seen_masks,
                &mut results,
            );
        }
    }
    results
}

pub fn enumerate_melds(mask_hi: u64, mask_lo: u64) -> Vec<Meld> {
    let (cards, jokers) = collect_cards(mask_hi, mask_lo);
    let mut melds = enumerate_sets(&cards, &jokers);
    melds.extend(enumerate_runs(&cards));
    melds.sort_by(|a, b| {
        (a.mask_hi, a.mask_lo, a.kind, a.jokers_used, a.points).cmp(&(
            b.mask_hi,
            b.mask_lo,
            b.kind,
            b.jokers_used,
            b.points,
        ))
    });
    melds
}
