"""穴帯(7-12番人気)に限定した層別置換検定と、loose版の頑健性確認。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vline import load, build, is_vline, band
from vline2 import collect, perm_test, boot_ci
import vline2

races = load()
for mode in ('strict', 'loose'):
    hist = build(races, mode)
    rows, _ = collect(races, hist)
    print(f'\n########## 向こう正面={mode} ##########')
    for name, sub in (('全帯', rows),
                      ('穴帯(7-12)のみ', [r for r in rows if r['band'] == '穴']),
                      ('穴＋大穴(7番人気以下)', [r for r in rows if r['band'] in ('穴','大穴')])):
        nv = sum(r['v'] for r in sub)
        print(f'\n--- {name}  n={len(sub)}  V={nv} ---')
        if nv < 20: print('  [不足] V群が小さすぎます'); continue
        print(f'{"指標":<10}{"V群":>11}{"非V群":>11}{"差":>11}{"両側p":>9}{"Bonf(8)":>10}')
        for key, lab in (('p3','複勝率'), ('win','勝率'), ('fuku','複勝回収'), ('tan','単勝回収')):
            a, na, b, nb, d, p = perm_test(sub, key, lambda r: r['pop'])
            f = (lambda x: f'{x*100:.4f}%') if key in ('p3','win') else (lambda x: f'{x:.2f}円')
            print(f'{lab:<10}{f(a):>11}{f(b):>11}{f(d):>11}{p:>9.4f}{min(1.0,p*8):>10.4f}')
