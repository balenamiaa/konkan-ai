//! Rust meld solver for Konkan.

use pyo3::prelude::*;
use pyo3::types::PyModule;

mod bitset;
mod cover;
mod deck;
mod runs_sets;

pub use deck::JOKER_IDS;

pub const OBJ_MAX_CARDS: u8 = 0;
pub const OBJ_MIN_DEADWOOD: u8 = 1;
pub const OBJ_FIRST_14: u8 = 2;

#[pyclass]
#[derive(Clone)]
pub struct Meld {
    #[pyo3(get)]
    pub mask_hi: u64,
    #[pyo3(get)]
    pub mask_lo: u64,
    #[pyo3(get)]
    pub points: i32,
    #[pyo3(get)]
    pub jokers_used: u8,
    #[pyo3(get)]
    pub kind: u8,
}

#[pyclass]
pub struct CoverResult {
    #[pyo3(get)]
    pub melds: Vec<Meld>,
    #[pyo3(get)]
    pub covered_cards: u8,
    #[pyo3(get)]
    pub total_points: i32,
    #[pyo3(get)]
    pub used_jokers: u8,
}

#[pyfunction]
fn enumerate_melds(mask_hi: u64, mask_lo: u64) -> PyResult<Vec<Meld>> {
    Ok(runs_sets::enumerate_melds(mask_hi, mask_lo))
}

#[pyfunction]
fn best_cover(mask_hi: u64, mask_lo: u64, objective: u8, threshold: i32) -> PyResult<CoverResult> {
    Ok(cover::best_cover(mask_hi, mask_lo, objective, threshold))
}

#[pymodule]
fn konkan_melds(_py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(enumerate_melds, module)?)?;
    module.add_function(wrap_pyfunction!(best_cover, module)?)?;
    module.add_class::<Meld>()?;
    module.add_class::<CoverResult>()?;
    Ok(())
}
