"""
Surface-adjusted Elo rating engine for CourtQuant.
"""

import numpy as np

class SurfaceEloEngine:
    def __init__(self, base_elo: float = 1500.0, k_factor: float = 32.0):
        self.base_elo = base_elo
        self.k_factor = k_factor
        self.overall_elo = {}
        self.surface_elo = {}

    def get_blended_elo(self, player_id: int, surface: str, surface_weight: float = 0.6) -> float:
        o_elo = self.overall_elo.get(player_id, self.base_elo)
        s_elo = self.surface_elo.get((player_id, surface), self.base_elo)
        return (surface_weight * s_elo) + ((1.0 - surface_weight) * o_elo)

    def calculate_win_probability(self, elo_a: float, elo_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))

    def update_ratings(self, winner_id: int, loser_id: int, surface: str, tourney_id: str):
        w_o = self.overall_elo.get(winner_id, self.base_elo)
        l_o = self.overall_elo.get(loser_id, self.base_elo)
        p_w_o = self.calculate_win_probability(w_o, l_o)
        
        self.overall_elo[winner_id] = w_o + self.k_factor * (1.0 - p_w_o)
        self.overall_elo[loser_id] = l_o + self.k_factor * (0.0 - (1.0 - p_w_o))
        
        w_s = self.surface_elo.get((winner_id, surface), self.base_elo)
        l_s = self.surface_elo.get((loser_id, surface), self.base_elo)
        p_w_s = self.calculate_win_probability(w_s, l_s)
        
        self.surface_elo[(winner_id, surface)] = w_s + self.k_factor * (1.0 - p_w_s)
        self.surface_elo[(loser_id, surface)] = l_s + self.k_factor * (0.0 - (1.0 - p_w_s))
