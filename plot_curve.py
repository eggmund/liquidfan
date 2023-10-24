import liquidfan as lf
import matplotlib.pyplot as plt
import numpy as np

for i in range(len(lf.FAN_CONFIGS)):
    T = np.linspace(0, 100, num=200)
    s = np.array([lf.get_speed_from_curve(t, lf.FAN_CONFIGS[i]) for t in T])
    plt.plot(T, s, label=lf.FAN_CONFIG_NAMES[i])

plt.title("liquidfan fan curves.")
plt.xlabel("Liquid temperature (C)")
plt.ylabel("Fan speed (from 0 -> 1).")
plt.legend()
plt.show()

