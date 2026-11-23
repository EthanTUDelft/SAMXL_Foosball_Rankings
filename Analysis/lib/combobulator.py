import os
import pandas as pd
import matplotlib.pyplot as plt

class Combobulator:

    def __init__(self, path_to_results):
        self.results = pd.read_csv(path_to_results)

    def matches_played(self,player_name,plot=False):
        return