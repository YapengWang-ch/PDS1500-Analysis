#!/usr/bin/env python3
"""
file_all.py — PDS1500 数据分析 (Python 版)

将 MATLAB 的 file_all.m 翻译为 Python + numpy + matplotlib 实现。

功能:
  1. 读取 PDS1500 二进制数据文件 (uint16 LE)
  2. 按 8 板 × 8 通道分离数据
  3. 提取触发阈值、时间戳、触发计数
  4. 提取波形数据 (每通道 1000 个采样点)
  5. 分析指定通道的最小值 (通过 config.txt 配置)
  6. 输出直方图和波形图 (PNG)

用法:
  python file_all.py <input.bin> [-c config.txt] [-o output_dir]

依赖:
  numpy, matplotlib
"""

import sys
import os
import time
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 无 GUI 后端, 直接输出 PNG
import matplotlib.pyplot as plt
from pathlib import Path

# 数据读取模块
from pds1500_reader import (
    BOARD_NUM,
    CHANNEL_NUM,
    SAMPLES_PER_BOARD,
    WAVEFORM_LEN,
    read_binary,
    separate_boards,
    extract_trigger_threshold,
    extract_timestamps,
    extract_triggers,
    extract_waveform,
    load_pds1500_file,
)


# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG = {
    'analysis_channels': 'B1C1, B1C7',
    'all_threshold': 14900,
    'event_threshold': 14820,
    'output_dir': './output',
    'output_dpi': 150,
    'histograms_enabled': True,
    'histograms_bins': 400,
    'waveform_overlay_enabled': True,
    'waveform_overlay_max_events': 200,
    'single_event_waveforms_enabled': True,
    'single_event_waveforms_max_events': 50,
    'trigger_rate_plot_enabled': True,
    'max_events': 0,
    'pretrigger_samples': 20,
    'waveform_length': 1000,
}


# ============================================================
# TXT 配置文件解析
# ============================================================

def _parse_bool(val):
    """将字符串解析为 bool"""
    return val.strip().lower() in ('true', 'yes', '1', 'on')


def _parse_int(val):
    """将字符串解析为 int"""
    return int(val.strip())


def _parse_channels(val):
    """解析通道列表: 'B1C1, B1C7, B2C3' -> [(0,0,'B1C1'), (0,6,'B1C7'), (1,2,'B2C3')]"""
    channels = []
    for item in val.split(','):
        item = item.strip()
        if not item:
            continue
        item_upper = item.upper()
        if item_upper.startswith('B') and 'C' in item_upper:
            try:
                b_part = item_upper[1:item_upper.index('C')]
                c_part = item_upper[item_upper.index('C') + 1:]
                board = int(b_part)
                channel = int(c_part)
                label = f"B{board}C{channel}"
                channels.append((board - 1, channel - 1, label))
            except ValueError:
                print(f"Warning: cannot parse channel '{item}', skipping")
    return channels


# 配置项解析器映射
_CONFIG_PARSERS = {
    'analysis_channels':              _parse_channels,
    'all_threshold':                  _parse_int,
    'event_threshold':                _parse_int,
    'output_dir':                    str.strip,
    'output_dpi':                    _parse_int,
    'histograms_enabled':            _parse_bool,
    'histograms_bins':               _parse_int,
    'waveform_overlay_enabled':      _parse_bool,
    'waveform_overlay_max_events':   _parse_int,
    'single_event_waveforms_enabled': _parse_bool,
    'single_event_waveforms_max_events': _parse_int,
    'trigger_rate_plot_enabled':     _parse_bool,
    'max_events':                    _parse_int,
    'pretrigger_samples':            _parse_int,
    'waveform_length':               _parse_int,
}


def load_txt_config(config_path=None):
    """
    加载 TXT 配置文件.
    优先级: 指定路径 > 脚本同目录 config.txt > 默认配置

    文件格式:
      key = value
      # 注释
    """
    if config_path and os.path.isfile(config_path):
        pass
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(script_dir, 'config.txt')
        if os.path.isfile(default_path):
            config_path = default_path

    if config_path and os.path.isfile(config_path):
        print(f"Loading config from: {config_path}")
        cfg = DEFAULT_CONFIG.copy()
        with open(config_path, 'r') as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip()
                if key in _CONFIG_PARSERS:
                    try:
                        cfg[key] = _CONFIG_PARSERS[key](val)
                    except Exception as e:
                        print(f"Warning: config line {lineno}: {e}")
                else:
                    print(f"Warning: unknown config key '{key}' at line {lineno}")
        return cfg
    else:
        print("No config file found, using default configuration.")
        return DEFAULT_CONFIG.copy()


def parse_channels(cfg):
    """
    从配置中解析通道列表.
    返回: list of (board_index_0based, channel_index_0based, label)
    """
    val = cfg.get('analysis_channels', '')
    if isinstance(val, list):
        return val
    elif isinstance(val, str):
        return _parse_channels(val)
    return []


def analyze_channels(data_all, event_size, channels, cfg):
    """
    分析指定通道的最小值.
    
    参数:
      data_all:   (event_size, 8, 8, 1000) ndarray
      event_size: 事件数
      channels:   list of (board_idx, channel_idx, label)
      cfg:        配置字典
    
    返回:
      results: dict, 每个通道的分析结果
    """
    all_threshold = cfg['all_threshold']
    event_threshold = cfg['event_threshold']
    max_events = cfg.get('max_events', 0)
    n_events = event_size if max_events <= 0 else min(event_size, max_events)

    results = {}

    for board_idx, ch_idx, label in channels:
        all_min_voltages = []
        all_min_indices = []
        event_voltages = []
        event_indices = []
        event_count = 0

        for ev in range(n_events):
            waveform = data_all[ev, board_idx, ch_idx, :]
            min_idx = int(np.argmin(waveform))
            min_val = waveform[min_idx]

            if min_val < all_threshold:
                all_min_voltages.append(min_val)
                all_min_indices.append(min_idx)
            if min_val < event_threshold:
                event_count += 1
                event_voltages.append(min_val)
                event_indices.append(min_idx)

            if (ev + 1) % 100 == 0:
                print(f"  [{label}] Processed event {ev + 1}/{n_events}")

        results[label] = {
            'all_min_voltages': np.array(all_min_voltages, dtype=np.uint16),
            'all_min_indices':  np.array(all_min_indices, dtype=np.uint16),
            'event_voltages':   np.array(event_voltages, dtype=np.uint16),
            'event_indices':    np.array(event_indices, dtype=np.uint16),
            'event_count':      event_count,
            'all_count':        len(all_min_voltages),
            'board_idx':        board_idx,
            'channel_idx':      ch_idx,
        }

        print(f"  [{label}] all={len(all_min_voltages)}, events={event_count}")

    print("Analysis complete.")
    return results


def compute_trigger_rate(time_num, trig_num, event_size):
    """
    计算触发率信息.
    MATLAB 原版:
      time_diff(:,i) = time_num(:,i) - time_num(:,1);
      trig_diff(:,i) = trig_num(:,i) - trig_num(:,1);
      trig_err1 = sum(trig_diff);  trig_err2 = sum(trig_err1);
      Trigger_rate = 4096*file_i/(time_num(4096,1)*4/1000/1000/1000);
    """
    # 时间差 (相对于 channel 0)
    time_diff = time_num.astype(np.int64) - time_num[:, 0:1].astype(np.int64)
    time_err = np.sum(time_diff)

    # 触发计数差
    trig_diff = trig_num.astype(np.int64) - trig_num[:, 0:1].astype(np.int64)
    trig_err1 = np.sum(trig_diff, axis=0)  # 每通道求和
    trig_err2 = np.sum(trig_err1)

    # 触发率: 基于第一个事件的时间戳计算
    # MATLAB: Trigger_rate = 4096*file_i/(time_num(4096,1)*4/1000/1000/1000)
    # time_num 单位是 4ns ticks (250 MHz clock)
    # 取最后一个有效事件的时间戳
    last_ev = min(event_size, 4096) - 1
    if last_ev >= 0 and time_num[last_ev, 0] > 0:
        time_seconds = time_num[last_ev, 0] * 4e-9  # 4ns per tick
        trigger_rate_hz = event_size / time_seconds if time_seconds > 0 else 0
        trigger_rate_khz = trigger_rate_hz / 1000.0
    else:
        trigger_rate_hz = 0
        trigger_rate_khz = 0

    # 每个通道的触发计数总和
    trig_sum_per_channel = np.sum(trig_num, axis=0)  # (64,)

    rate_info = {
        'time_diff': time_diff,
        'time_err': time_err,
        'trig_diff': trig_diff,
        'trig_err1': trig_err1,
        'trig_err2': trig_err2,
        'trigger_rate_hz': trigger_rate_hz,
        'trigger_rate_khz': trigger_rate_khz,
        'trig_sum_per_channel': trig_sum_per_channel,
    }
    return rate_info


def plot_trigger_rate(rate_info, output_dir, dpi=150):
    """
    绘制触发率相关图表:
      - 每通道触发计数分布
      - 触发计数差 (trig_err1)
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 左图: 每通道总触发计数
    axes[0].bar(range(64), rate_info['trig_sum_per_channel'])
    axes[0].set_title('Total Trigger Count per Channel')
    axes[0].set_xlabel('Channel (0-63)')
    axes[0].set_ylabel('Total Trigger Count')
    axes[0].set_yscale('log')

    # 右图: trig_err1 (触发计数差之和)
    axes[1].bar(range(64), rate_info['trig_err1'])
    axes[1].set_title('Sum of Trigger Count Differences (trig_err1)')
    axes[1].set_xlabel('Channel (0-63)')
    axes[1].set_ylabel('Sum of Differences')
    axes[1].axhline(y=0, color='r', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure_trigger_rate.png')
    fig.savefig(outpath, dpi=dpi)
    plt.close(fig)
    print(f"Saved {outpath}")

def plot_histograms(results, cfg, output_dir):
    """
    绘制直方图.
    每个通道 4 张子图: all_voltages, all_indices, event_voltages, event_indices
    动态布局: n_channels 行 x 4 列
    """
    channels = list(results.keys())  # 保持顺序
    n_channels = len(channels)

    if n_channels == 0:
        print("No channels to plot histograms for.")
        return

    bins = cfg.get('histograms_bins', 400)
    dpi = cfg.get('output_dpi', 150)

    fig, axes = plt.subplots(n_channels, 4, figsize=(20, 5 * n_channels))
    if n_channels == 1:
        axes = axes.reshape(1, -1)

    for row, label in enumerate(channels):
        r = results[label]
        data_pairs = [
            (r['all_min_voltages'], f'{label} Min Voltages (all <{cfg["all_threshold"]})', 'Voltage'),
            (r['all_min_indices'],  f'{label} Min Indices (all <{cfg["all_threshold"]})',  'Index'),
            (r['event_voltages'],   f'{label} Min Voltages (event <{cfg["event_threshold"]})', 'Voltage'),
            (r['event_indices'],    f'{label} Min Indices (event <{cfg["event_threshold"]})',  'Index'),
        ]
        for col, (data, title, xlabel) in enumerate(data_pairs):
            ax = axes[row, col]
            if len(data) > 0:
                ax.hist(data, bins=bins)
                ax.set_yscale('log')
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel('Frequency')

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure_histograms.png')
    fig.savefig(outpath, dpi=dpi)
    plt.close(fig)
    print(f"Saved {outpath}")


def plot_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir):
    """
    波形叠加图: 每个通道一个子图, 叠加前 N 个事件的波形
    """
    max_events = min(event_size, cfg.get('waveform_overlay_max_events', 200))
    n_channels = len(channels)
    dpi = cfg.get('output_dpi', 150)

    if n_channels == 0:
        return

    n_cols = min(n_channels, 4)
    n_rows = (n_channels + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
    if n_channels == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for idx, (board_idx, ch_idx, label) in enumerate(channels):
        ax = axes[idx]
        for ev in range(max_events):
            wf = data_all[ev, board_idx, ch_idx, :]
            ax.plot(wf, linewidth=0.5, alpha=0.5)
        ax.axhline(y=trigger_threshold[board_idx, ch_idx], color='r', linestyle='--',
                   label=f'Threshold={trigger_threshold[board_idx, ch_idx]}')
        ax.set_title(f'Board {board_idx + 1}, Channel {ch_idx + 1} ({label})')
        ax.set_xlabel('Sample')
        ax.set_ylabel('ADC Value')
        ax.legend()

    for idx in range(n_channels, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure_waveforms_overlay.png')
    fig.savefig(outpath, dpi=dpi)
    plt.close(fig)
    print(f"Saved {outpath}")


def plot_single_event_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir):
    """
    逐个事件绘制波形: 每个事件一张图, 每个通道一个子图
    """
    max_events = min(event_size, cfg.get('single_event_waveforms_max_events', 50))
    n_channels = len(channels)
    dpi = cfg.get('output_dpi', 150)

    if n_channels == 0:
        return

    n_cols = min(n_channels, 4)
    n_rows = (n_channels + n_cols - 1) // n_cols

    for ev in range(max_events):
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        if n_channels == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        for idx, (board_idx, ch_idx, label) in enumerate(channels):
            ax = axes[idx]
            wf = data_all[ev, board_idx, ch_idx, :]
            ax.plot(wf)
            ax.axhline(y=trigger_threshold[board_idx, ch_idx], color='r', linestyle='--')
            ax.set_title(f'Event {ev}, {label}')
            ax.set_xlabel('Sample')
            ax.set_ylabel('ADC Value')

        for idx in range(n_channels, len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        outpath = os.path.join(output_dir, f'event_{ev:04d}_waveforms.png')
        fig.savefig(outpath, dpi=dpi)
        plt.close(fig)

        if (ev + 1) % 10 == 0:
            print(f"  Saved {ev + 1}/{max_events} event waveform plots")

    print(f"Saved {max_events} event waveform plots to {output_dir}/")


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='PDS1500 Analysis - Python version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_all.py data.bin
  python file_all.py data.bin -c my_config.txt
  python file_all.py data.bin -c config.txt -o ./results
        """
    )
    parser.add_argument('input', help='PDS1500 binary data file (uint16 LE)')
    parser.add_argument('-c', '--config', default=None, help='Configuration file (default: config.txt)')
    parser.add_argument('-o', '--output', default=None, help='Output directory (overrides config)')
    args = parser.parse_args()

    # ---- 加载配置 ----
    cfg = load_txt_config(args.config)

    # 解析通道
    channels = parse_channels(cfg)
    if not channels:
        print("Error: no analysis channels specified in config.")
        print("  Add 'analysis_channels = B1C1, B1C7' to config.txt")
        sys.exit(1)

    print("Configured channels:")
    for _, _, label in channels:
        print(f"  - {label}")

    # 输出目录: 命令行 > 配置文件 > 默认
    output_dir = args.output or cfg.get('output_dir', './output')
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 50)
    print("  PDS1500 Analysis (Python version)")
    print(f"  Input:  {args.input}")
    print(f"  Output: {output_dir}")
    print("=" * 50)

    t_start = time.time()

    # ---- 步骤 1: 读取二进制文件 ----
    print("\n[1/7] Reading binary file...")
    data = read_binary(args.input)

    # ---- 步骤 2: 按板子分离 ----
    print("[2/7] Separating boards...")
    board_data, event_size = separate_boards(data)
    del data

    # ---- 步骤 3: 提取触发阈值 ----
    print("[3/7] Extracting trigger thresholds...")
    trigger_threshold = extract_trigger_threshold(board_data)

    # ---- 步骤 4: 提取时间戳 & 触发计数 ----
    print("[4/7] Extracting timestamps and trigger counts...")
    time_num = extract_timestamps(board_data, event_size)
    trig_num = extract_triggers(board_data, event_size)

    # ---- 步骤 5: 计算触发率 ----
    print("[5/7] Computing trigger rates...")
    rate_info = compute_trigger_rate(time_num, trig_num, event_size)

    # ---- 步骤 6: 提取波形数据 ----
    print("[6/7] Extracting waveform data...")
    data_all = extract_waveform(board_data, event_size)
    del board_data

    # ---- 步骤 7: 分析通道 ----
    print("[7/7] Analyzing channels...")
    results = analyze_channels(data_all, event_size, channels, cfg)

    # ---- 绘图 ----
    print("\nGenerating plots...")

    if cfg.get('histograms_enabled', True):
        print("  Plotting histograms...")
        plot_histograms(results, cfg, output_dir)

    if cfg.get('waveform_overlay_enabled', True):
        print("  Plotting waveform overlay...")
        plot_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir)

    if cfg.get('single_event_waveforms_enabled', True):
        print("  Plotting individual event waveforms...")
        plot_single_event_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir)

    if cfg.get('trigger_rate_plot_enabled', True):
        print("  Plotting trigger rate...")
        plot_trigger_rate(rate_info, output_dir, cfg.get('output_dpi', 150))

    # ---- 汇总 ----
    t_end = time.time()

    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)
    print(f"  Total events:              {event_size}")
    print(f"  Thresholds:                all={cfg['all_threshold']}, event={cfg['event_threshold']}")
    for label in results:
        r = results[label]
        rate = r['event_count'] / event_size
        print(f"  {label}: events(<{cfg['event_threshold']})={r['event_count']}, "
              f"rate={rate:.6f}, all(<{cfg['all_threshold']})={r['all_count']}")
    print(f"  --- Trigger Rate ---")
    print(f"  System trigger rate:       {rate_info['trigger_rate_hz']:.2f} Hz "
          f"({rate_info['trigger_rate_khz']:.3f} kHz)")
    print(f"  Time error (sum time_diff): {rate_info['time_err']}")
    print(f"  Trig error1 range:         [{np.min(rate_info['trig_err1'])}, {np.max(rate_info['trig_err1'])}]")
    print(f"  Trig error2 (total sum):   {rate_info['trig_err2']}")
    print(f"  Elapsed time:              {t_end - t_start:.2f} seconds")
    print(f"\n  Output saved to: {output_dir}/")
    print("Done.")
    print(f"\n  Output saved to: {output_dir}/")
    print("Done.")


if __name__ == '__main__':
    main()
