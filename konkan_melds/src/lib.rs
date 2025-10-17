//! Rust meld solver scaffolding for Konkan.

use pyo3::prelude::*;

#[pyclass]
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
fn enumerate_melds(_mask_hi: u64, _mask_lo: u64) -> PyResult<Vec<Meld>> {
    Ok(Vec::new())
}

#[pyfunction]
fn best_cover(_mask_hi: u64, _mask_lo: u64, _objective: u8, _threshold: i32) -> PyResult<CoverResult> {
    Ok(CoverResult {
        melds: Vec::new(),
        covered_cards: 0,
        total_points: 0,
        used_jokers: 0,
    })
}

#[pymodule]
fn konkan_melds(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(enumerate_melds, m)?)?;
    m.add_function(wrap_pyfunction!(best_cover, m)?)?;
    m.add_class::<Meld>()?;
    m.add_class::<CoverResult>()?;
    Ok(())
}
