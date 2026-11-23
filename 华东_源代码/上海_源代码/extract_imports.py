import pickle
import sys
from collections import Counter, defaultdict
from math import hypot
from pathlib import Path

work = Path(__file__).parent
sys.path.insert(0, str(work / 'geo'))

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box


def read():
    with (work / 'extract.pkl').open('rb') as handle:
        return pickle.load(handle)
