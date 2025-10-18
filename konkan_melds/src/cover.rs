//! Search utilities for selecting the best meld cover under various objectives.

use std::cmp::Ordering;

use crate::bitset::merge_words;
use crate::runs_sets::enumerate_melds;
use crate::{CoverResult, Meld, OBJ_FIRST_14, OBJ_MAX_CARDS, OBJ_MIN_DEADWOOD};

#[derive(Clone, Copy)]
struct Score {
    meets_threshold: bool,
    target_met: bool,
    covered_cards: u8,
    deadwood: u8,
    total_points: i32,
    used_jokers: u8,
}

fn better_score(objective: u8, new: &Score, best: &Score) -> bool {
    match objective {
        OBJ_MIN_DEADWOOD => match (new.meets_threshold, best.meets_threshold) {
            (true, false) => true,
            (false, true) => false,
            _ => {
                match new.deadwood.cmp(&best.deadwood) {
                    Ordering::Less => return true,
                    Ordering::Greater => return false,
                    Ordering::Equal => {}
                }
                match new.total_points.cmp(&best.total_points) {
                    Ordering::Greater => return true,
                    Ordering::Less => return false,
                    Ordering::Equal => {}
                }
                match new.covered_cards.cmp(&best.covered_cards) {
                    Ordering::Greater => return true,
                    Ordering::Less => return false,
                    Ordering::Equal => {}
                }
                new.used_jokers < best.used_jokers
            }
        },
        OBJ_FIRST_14 => match (new.target_met, best.target_met) {
            (true, false) => true,
            (false, true) => false,
            _ => {
                match new.deadwood.cmp(&best.deadwood) {
                    Ordering::Less => return true,
                    Ordering::Greater => return false,
                    Ordering::Equal => {}
                }
                match new.covered_cards.cmp(&best.covered_cards) {
                    Ordering::Greater => return true,
                    Ordering::Less => return false,
                    Ordering::Equal => {}
                }
                match new.total_points.cmp(&best.total_points) {
                    Ordering::Greater => return true,
                    Ordering::Less => return false,
                    Ordering::Equal => {}
                }
                new.used_jokers < best.used_jokers
            }
        },
        OBJ_MAX_CARDS | _ => {
            match new.covered_cards.cmp(&best.covered_cards) {
                Ordering::Greater => return true,
                Ordering::Less => return false,
                Ordering::Equal => {}
            }
            match new.total_points.cmp(&best.total_points) {
                Ordering::Greater => return true,
                Ordering::Less => return false,
                Ordering::Equal => {}
            }
            match new.deadwood.cmp(&best.deadwood) {
                Ordering::Less => return true,
                Ordering::Greater => return false,
                Ordering::Equal => {}
            }
            new.used_jokers < best.used_jokers
        }
    }
}

fn update_best(
    objective: u8,
    threshold: i32,
    total_cards: u8,
    current_mask: u128,
    current_points: i32,
    current_jokers: u8,
    selection: &[usize],
    best: &mut Option<(Score, Vec<usize>, i32, u8, u128)>,
) {
    let covered_cards = current_mask.count_ones() as u8;
    let deadwood = total_cards.saturating_sub(covered_cards);
    let score = Score {
        meets_threshold: current_points >= threshold,
        target_met: covered_cards >= 14,
        covered_cards,
        deadwood,
        total_points: current_points,
        used_jokers: current_jokers,
    };

    match best {
        None => {
            *best = Some((score, selection.to_vec(), current_points, current_jokers, current_mask));
        }
        Some((best_score, _, _, _, _)) => {
            if better_score(objective, &score, best_score) {
                *best = Some((score, selection.to_vec(), current_points, current_jokers, current_mask));
            }
        }
    }
}

fn search_best_cover(
    idx: usize,
    current_mask: u128,
    current_points: i32,
    current_jokers: u8,
    selection: &mut Vec<usize>,
    masks: &[u128],
    points: &[i32],
    jokers_used: &[u8],
    objective: u8,
    threshold: i32,
    total_cards: u8,
    best: &mut Option<(Score, Vec<usize>, i32, u8, u128)>,
) {
    update_best(
        objective,
        threshold,
        total_cards,
        current_mask,
        current_points,
        current_jokers,
        selection,
        best,
    );

    if idx == masks.len() {
        return;
    }

    // Skip current meld.
    search_best_cover(
        idx + 1,
        current_mask,
        current_points,
        current_jokers,
        selection,
        masks,
        points,
        jokers_used,
        objective,
        threshold,
        total_cards,
        best,
    );

    let meld_mask = masks[idx];
    if current_mask & meld_mask != 0 {
        return;
    }

    selection.push(idx);
    search_best_cover(
        idx + 1,
        current_mask | meld_mask,
        current_points + points[idx],
        current_jokers + jokers_used[idx],
        selection,
        masks,
        points,
        jokers_used,
        objective,
        threshold,
        total_cards,
        best,
    );
    selection.pop();
}

pub fn best_cover(mask_hi: u64, mask_lo: u64, objective: u8, threshold: i32) -> CoverResult {
    let melds = enumerate_melds(mask_hi, mask_lo);
    if melds.is_empty() {
        return CoverResult {
            melds,
            covered_cards: 0,
            total_points: 0,
            used_jokers: 0,
        };
    }

    let masks: Vec<u128> = melds
        .iter()
        .map(|meld| merge_words(meld.mask_hi, meld.mask_lo))
        .collect();
    let points: Vec<i32> = melds.iter().map(|meld| meld.points).collect();
    let jokers_used: Vec<u8> = melds.iter().map(|meld| meld.jokers_used).collect();

    let total_cards = merge_words(mask_hi, mask_lo).count_ones() as u8;

    let mut best: Option<(Score, Vec<usize>, i32, u8, u128)> = None;
    let mut selection = Vec::new();
    search_best_cover(
        0,
        0,
        0,
        0,
        &mut selection,
        &masks,
        &points,
        &jokers_used,
        objective,
        threshold,
        total_cards,
        &mut best,
    );

    let (score, indices, total_points, used_jokers, _) = best.unwrap();
    let mut chosen_melds: Vec<Meld> = indices.into_iter().map(|idx| melds[idx].clone()).collect();
    chosen_melds.sort_by(|a, b| {
        (a.mask_hi, a.mask_lo, a.kind, a.jokers_used, a.points).cmp(&(b.mask_hi, b.mask_lo, b.kind, b.jokers_used, b.points))
    });

    CoverResult {
        melds: chosen_melds,
        covered_cards: score.covered_cards,
        total_points,
        used_jokers,
    }
}
