#!/usr/bin/env python3
"""
file_all.py — PDS1500 数据分析 (Python 版)

将 MATLAB 的 file_all.m 翻译为 Python + numpy + matplotlib 实现。

功能:
  1. 读取 PDS1500 二进制数据文件 (uint16 LE)
  2. 按 8 板 × 8 通道分离数据
  3. 提取触发阈值、时间戳、触发计数
  4. 提取波形数据 (每通道 1000 个采样点)
  5. 分析 Channel 1 和 Channel 7 的最小值
  6. 输出直方图和波形图 (PNG)

用法:
  python file_all.py <input.bin> [output_dir]

依赖:
  numpy, matplotlib
"""

import sys
import os
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 无 GUI 后端, 直接输出 PNG
import matplotlib.pyplot as plt
from pathlib import Path


# ============================================================
# 常量
# ============================================================
BOARD_NUM = 8
CHANNEL_NUM = 8
SAMPLES_PER_BOARD = 8192
WAVEFORM_LEN = 1000


def read_binary(filename):
    """读取 uint16 little-endian 二进制文件"""
    data = np.fromfile(filename, dtype=np.uint16)
    print(f"Read {len(data)} samples from {filename}")
    return data


def separate_boards(data):
    """
    按板子分离数据.
    每个事件 = 65536 samples = 8 boards × 8192 samples/board.
    返回: list of 8 arrays, 每个 shape = (event_size * 8192,)
    """
    data_end = len(data)
    data_size = data_end // CHANNEL_NUM          # 每个板子的总数据量
    event_size = data_size // SAMPLES_PER_BOARD   # 事件数
    print(f"data_size={data_size}, event_size={event_size}")

    # 将原始数据 reshape 为 (event_size, 65536)
    total_per_event = BOARD_NUM * SAMPLES_PER_BOARD  # 65536
    usable = event_size * total_per_event
    data_trimmed = data[:usable].reshape(event_size, total_per_event)

    # 拆分为 8 个板子: 每个 shape = (event_size, 8192)
    board_data = []
    for b in range(BOARD_NUM):
        bd = data_trimmed[:, b * SAMPLES_PER_BOARD : (b + 1) * SAMPLES_PER_BOARD]
        board_data.append(bd)

    print("Board separation complete.")
    return board_data, event_size


def extract_trigger_threshold(board_data):
    """
    提取触发阈值: 每个 channel 的第 1017 个 sample (1-indexed → index 1016)
    返回: (8, 8) ndarray
    """
    trigger_threshold = np.zeros((BOARD_NUM, CHANNEL_NUM), dtype=np.uint16)
    for b in range(BOARD_NUM):
        for c in range(CHANNEL_NUM):
            # MATLAB: 1024*(i-1)+1017 → Python: 1024*c + 1016
            trigger_threshold[b, c] = board_data[b][0, 1024 * c + 1016]
    print("Trigger thresholds extracted.")
    return trigger_threshold


def extract_timestamps(board_data, event_size):
    """
    提取时间戳.
    MATLAB: v0*16^0 + v1*16^4 + v2*16^8 + v3*16^12
    即: v0 + v1*65536 + v2*65536^2 + v3*65536^3
    返回: (event_size, 64) ndarray
    """
    time_num = np.zeros((event_size, 64), dtype=np.uint64)

    for c in range(CHANNEL_NUM):
        base = 1024 * c
        # MATLAB 1-indexed: 1009,1010,1011,1012 → Python: 1008,1009,1010,1011
        t0, t1, t2, t3 = base + 1008, base + 1009, base + 1010, base + 1011

        for b in range(BOARD_NUM):
            col = b * 8 + c
            v0 = board_data[b][:, t0].astype(np.uint64)
            v1 = board_data[b][:, t1].astype(np.uint64)
            v2 = board_data[b][:, t2].astype(np.uint64)
            v3 = board_data[b][:, t3].astype(np.uint64)
            time_num[:, col] = v0 + v1 * 65536 + v2 * 4294967296 + v3 * 281474976710656

    print("Timestamps extracted.")
    return time_num


def extract_triggers(board_data, event_size):
    """
    提取触发计数.
    返回: (event_size, 64) ndarray
    """
    trig_num = np.zeros((event_size, 64), dtype=np.uint64)

    for c in range(CHANNEL_NUM):
        base = 1024 * c
        # MATLAB 1-indexed: 1013,1014,1015,1016 → Python: 1012,1013,1014,1015
        t0, t1, t2, t3 = base + 1012, base + 1013, base + 1014, base + 1015

        for b in range(BOARD_NUM):
            col = b * 8 + c
            v0 = board_data[b][:, t0].astype(np.uint64)
            v1 = board_data[b][:, t1].astype(np.uint64)
            v2 = board_data[b][:, t2].astype(np.uint64)
            v3 = board_data[b][:, t3].astype(np.uint64)
            trig_num[:, col] = v0 + v1 * 65536 + v2 * 4294967296 + v3 * 281474976710656

    print("Trigger counts extracted.")
    return trig_num


def extract_waveform(board_data, event_size):
    """
    提取波形数据.
    data_all[event, board, channel, :1000]
    MATLAB: 1024*(i-1)+9 : 1024*(i-1)+1008 → Python: 1024*c+8 : 1024*c+1008
    返回: (event_size, 8, 8, 1000) ndarray
    """
    data_all = np.zeros((event_size, BOARD_NUM, CHANNEL_NUM, WAVEFORM_LEN), dtype=np.uint16)

    for b in range(BOARD_NUM):
        for c in range(CHANNEL_NUM):
            base = 1024 * c
            start = base + 8       # MATLAB +9 (1-indexed)
            end = base + 1008      # MATLAB +1008 inclusive → Python :1008 exclusive
            data_all[:, b, c, :] = board_data[b][:, start:end]

    print("Waveform data extracted.")
    return data_all


def analyze_channels(data_all, event_size):
    """
    分析 Channel 1 和 Channel 7 的最小值.
    返回两组结果:
      - all_*:  min_voltage < 14900
      - event_*: min_voltage < 14820
    """
    all_min_voltages_ch1 = []
    all_min_indices_ch1 = []
    all_min_voltages_ch7 = []
    all_min_indices_ch7 = []

    event_voltages_ch1 = []
    event_indices_ch1 = []
    event_voltages_ch7 = []
    event_indices_ch7 = []

    event_ch1 = 0
    event_ch7 = 0

    board_id = 0  # 只分析 board 1

    for ev in range(event_size):
        # Channel 1 (index 0)
        waveform = data_all[ev, board_id, 0, :]
        min_idx = int(np.argmin(waveform))
        min_val = waveform[min_idx]

        if min_val < 14900:
            all_min_voltages_ch1.append(min_val)
            all_min_indices_ch1.append(min_idx)
        if min_val < 14820:
            event_ch1 += 1
            event_voltages_ch1.append(min_val)
            event_indices_ch1.append(min_idx)

        # Channel 7 (index 6)
        waveform = data_all[ev, board_id, 6, :]
        min_idx = int(np.argmin(waveform))
        min_val = waveform[min_idx]

        if min_val < 14900:
            all_min_voltages_ch7.append(min_val)
            all_min_indices_ch7.append(min_idx)
        if min_val < 14820:
            event_ch7 += 1
            event_voltages_ch7.append(min_val)
            event_indices_ch7.append(min_idx)

        if (ev + 1) % 100 == 0:
            print(f"  Processed event {ev + 1}/{event_size}")

    print("Analysis complete.")
    print(f"  CH1: all={len(all_min_voltages_ch1)}, events={event_ch1}")
    print(f"  CH7: all={len(all_min_voltages_ch7)}, events={event_ch7}")

    results = {
        'all_min_voltages_ch1': np.array(all_min_voltages_ch1, dtype=np.uint16),
        'all_min_indices_ch1':  np.array(all_min_indices_ch1, dtype=np.uint16),
        'all_min_voltages_ch7': np.array(all_min_voltages_ch7, dtype=np.uint16),
        'all_min_indices_ch7':  np.array(all_min_indices_ch7, dtype=np.uint16),
        'event_voltages_ch1':   np.array(event_voltages_ch1, dtype=np.uint16),
        'event_indices_ch1':    np.array(event_indices_ch1, dtype=np.uint16),
        'event_voltages_ch7':   np.array(event_voltages_ch7, dtype=np.uint16),
        'event_indices_ch7':    np.array(event_indices_ch7, dtype=np.uint16),
        'event_ch1': event_ch1,
        'event_ch7': event_ch7,
    }
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


def plot_trigger_rate(rate_info, output_dir):
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
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    print(f"Saved {outpath}")

def plot_histograms(results, output_dir):
    """
    对应 MATLAB figure(2): 8 个子图的直方图
    """
    fig, axes = plt.subplots(2, 4, figsize=(16, 10))

    data_pairs = [
        (results['all_min_voltages_ch1'], 'Channel 1 Min Voltages (all <14900)', 'Voltage', axes[0, 0]),
        (results['all_min_indices_ch1'],  'Channel 1 Min Indices (all <14900)',  'Index',   axes[0, 1]),
        (results['all_min_voltages_ch7'], 'Channel 7 Min Voltages (all <14900)', 'Voltage', axes[0, 2]),
        (results['all_min_indices_ch7'],  'Channel 7 Min Indices (all <14900)',  'Index',   axes[0, 3]),
        (results['event_voltages_ch1'],   'Channel 1 Min Voltages (event <14820)', 'Voltage', axes[1, 0]),
        (results['event_indices_ch1'],    'Channel 1 Min Indices (event <14820)',  'Index',   axes[1, 1]),
        (results['event_voltages_ch7'],   'Channel 7 Min Voltages (event <14820)', 'Voltage', axes[1, 2]),
        (results['event_indices_ch7'],    'Channel 7 Min Indices (event <14820)',  'Index',   axes[1, 3]),
    ]

    for data, title, xlabel, ax in data_pairs:
        if len(data) > 0:
            ax.hist(data, bins=400)
            ax.set_yscale('log')
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Frequency')

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure2_histograms.png')
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    print(f"Saved {outpath}")


def plot_waveforms(data_all, trigger_threshold, event_size, output_dir):
    """
    对应 MATLAB figure(3): 前 200 个事件的 Ch1/Ch7 波形图
    """
    n_events = min(event_size, 200)
    board_id = 0

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ev in range(n_events):
        # Channel 1
        wf1 = data_all[ev, board_id, 0, :]
        axes[0].plot(wf1, linewidth=0.5, alpha=0.5)
        # Channel 7
        wf7 = data_all[ev, board_id, 6, :]
        axes[1].plot(wf7, linewidth=0.5, alpha=0.5)

    # 画触发阈值线
    for ax, ch in zip(axes, [0, 6]):
        ax.axhline(y=trigger_threshold[board_id, ch], color='r', linestyle='--',
                   label=f'Threshold={trigger_threshold[board_id, ch]}')
        ax.set_title(f'Board 1, Channel {ch + 1}')
        ax.set_xlabel('Sample')
        ax.set_ylabel('ADC Value')
        ax.legend()

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure3_waveforms.png')
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    print(f"Saved {outpath}")


def plot_single_event_waveforms(data_all, trigger_threshold, event_size, output_dir):
    """
    对应 MATLAB parfor 内的 subplot(2,2,1) 和 subplot(2,2,2):
    逐个事件绘制 Ch1/Ch7 波形 (只保存前 50 个事件, 避免过多文件)
    """
    n_save = min(event_size, 50)
    board_id = 0

    for ev in range(n_save):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        for ax, ch in zip(axes, [0, 6]):
            wf = data_all[ev, board_id, ch, :]
            ax.plot(wf)
            ax.axhline(y=trigger_threshold[board_id, ch], color='r', linestyle='--')
            ax.set_title(f'Event {ev}, Board 1, Channel {ch + 1}')
            ax.set_xlabel('Sample')
            ax.set_ylabel('ADC Value')

        plt.tight_layout()
        outpath = os.path.join(output_dir, f'event_{ev:04d}_waveforms.png')
        fig.savefig(outpath, dpi=100)
        plt.close(fig)

        if (ev + 1) % 10 == 0:
            print(f"  Saved {ev + 1}/{n_save} event waveform plots")

    print(f"Saved {n_save} event waveform plots to {output_dir}/")


# ============================================================
# 主程序
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.bin> [output_dir]")
        print("  input.bin  - PDS1500 binary data file (uint16 LE)")
        print("  output_dir - output directory (default: ./output)")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else './output'

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 50)
    print("  PDS1500 Analysis (Python version)")
    print(f"  Input:  {input_file}")
    print(f"  Output: {output_dir}")
    print("=" * 50)

    t_start = time.time()

    # ---- 步骤 1: 读取二进制文件 ----
    print("\n[1/8] Reading binary file...")
    data = read_binary(input_file)

    # ---- 步骤 2: 按板子分离 ----
    print("[2/8] Separating boards...")
    board_data, event_size = separate_boards(data)
    del data  # 释放原始数据内存

    # ---- 步骤 3: 提取触发阈值 ----
    print("[3/8] Extracting trigger thresholds...")
    trigger_threshold = extract_trigger_threshold(board_data)

    # ---- 步骤 4: 提取时间戳 ----
    print("[4/8] Extracting timestamps...")
    time_num = extract_timestamps(board_data, event_size)

    # ---- 步骤 5: 提取触发计数 ----
    print("[5/8] Extracting trigger counts...")
    trig_num = extract_triggers(board_data, event_size)

    # ---- 步骤 6: 计算触发率 ----
    print("[6/8] Computing trigger rates...")
    rate_info = compute_trigger_rate(time_num, trig_num, event_size)

    # ---- 步骤 7: 提取波形数据 ----
    print("[7/8] Extracting waveform data...")
    data_all = extract_waveform(board_data, event_size)

    # 释放 board_data (后续只需要 data_all)
    del board_data

    # ---- 步骤 8: 分析 Channel 1 & 7 ----
    print("[8/8] Analyzing channels...")
    results = analyze_channels(data_all, event_size)

    # ---- 绘图 ----
    print("\nGenerating plots...")

    print("  Plotting histograms (Figure 2)...")
    plot_histograms(results, output_dir)

    print("  Plotting waveform overlay (Figure 3)...")
    plot_waveforms(data_all, trigger_threshold, event_size, output_dir)

    print("  Plotting individual event waveforms...")
    plot_single_event_waveforms(data_all, trigger_threshold, event_size, output_dir)

    print("  Plotting trigger rate...")
    plot_trigger_rate(rate_info, output_dir)

    # ---- 汇总 ----
    t_end = time.time()

    trigger_threshold_1_ch1 = 14820
    trigger_threshold_1_ch7 = 14820

    rate_ch1 = results['event_ch1'] / event_size
    rate_ch7 = results['event_ch7'] / event_size

    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)
    print(f"  Total events:              {event_size}")
    print(f"  CH1 trigger threshold:     {trigger_threshold_1_ch1}")
    print(f"  CH7 trigger threshold:     {trigger_threshold_1_ch7}")
    print(f"  CH1 events (<14820):       {results['event_ch1']}, rate={rate_ch1:.6f}")
    print(f"  CH7 events (<14820):       {results['event_ch7']}, rate={rate_ch7:.6f}")
    print(f"  CH1 all (<14900):          {len(results['all_min_voltages_ch1'])}")
    print(f"  CH7 all (<14900):          {len(results['all_min_voltages_ch7'])}")
    print(f"  --- Trigger Rate ---")
    print(f"  System trigger rate:       {rate_info['trigger_rate_hz']:.2f} Hz ({rate_info['trigger_rate_khz']:.3f} kHz)")
    print(f"  Time error (sum time_diff): {rate_info['time_err']}")
    print(f"  Trig error1 (sum per ch):  [{np.min(rate_info['trig_err1'])}, {np.max(rate_info['trig_err1'])}]")
    print(f"  Trig error2 (total sum):   {rate_info['trig_err2']}")
    print(f"  Elapsed time:              {t_end - t_start:.2f} seconds")
    print(f"\n  Output saved to: {output_dir}/")
    print("Done.")


if __name__ == '__main__':
    main()
