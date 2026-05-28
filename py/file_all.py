#!/usr/bin/env python
"""
file_all.py - PDS1500 data analysis (Python version)

Translation of MATLAB file_all.m to Python + numpy + matplotlib.

Features:
  1. Read PDS1500 binary data file (uint16 LE)
  2. Separate data by 8 boards x 8 channels
  3. Extract trigger thresholds, timestamps, trigger counts
  4. Extract waveform data (1000 samples per channel)
  5. Analyze minimum values of specified channels (via config.txt)
  6. Output histogram and waveform plots (PNG)

Usage:
  python file_all.py <input.bin> [-c config.txt] [-o output_dir]

Dependencies:
  numpy, matplotlib
"""

from __future__ import print_function, division
import sys
import os
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')  # non-GUI backend, output PNG directly
import matplotlib.pyplot as plt

# Data reader module
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
# Default configuration
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
# TXT config file parser
# ============================================================

def _parse_bool(val):
    """Parse string to bool."""
    return val.strip().lower() in ('true', 'yes', '1', 'on')


def _parse_int(val):
    """Parse string to int."""
    return int(val.strip())


def _parse_channels(val):
    """Parse channel list: 'B1C1, B1C7, B2C3' -> [(0,0,'B1C1'), (0,6,'B1C7'), (1,2,'B2C3')]"""
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
                label = "B{0}C{1}".format(board, channel)
                channels.append((board - 1, channel - 1, label))
            except ValueError:
                print("Warning: cannot parse channel '{0}', skipping".format(item))
    return channels


# Config item parser mapping
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
    Load TXT config file.

    Priority: specified path > config.txt in script dir > default config

    File format:
      key = value
      # comment
    """
    if config_path and os.path.isfile(config_path):
        pass
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(script_dir, 'config.txt')
        if os.path.isfile(default_path):
            config_path = default_path

    if config_path and os.path.isfile(config_path):
        print("Loading config from: {0}".format(config_path))
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
                        print("Warning: config line {0}: {1}".format(lineno, e))
                else:
                    print("Warning: unknown config key '{0}' at line {1}".format(key, lineno))
        return cfg
    else:
        print("No config file found, using default configuration.")
        return DEFAULT_CONFIG.copy()


def parse_channels(cfg):
    """
    Parse channel list from config.

    Returns:
        list of (board_index_0based, channel_index_0based, label)
    """
    val = cfg.get('analysis_channels', '')
    if isinstance(val, list):
        return val
    elif isinstance(val, str):
        return _parse_channels(val)
    return []


def analyze_channels(data_all, event_size, channels, cfg):
    """
    Analyze minimum values of specified channels.

    Args:
        data_all:   (event_size, 8, 8, 1000) ndarray
        event_size: number of events
        channels:   list of (board_idx, channel_idx, label)
        cfg:        config dict

    Returns:
        results: dict, analysis results per channel label
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
                print("  [{0}] Processed event {1}/{2}".format(label, ev + 1, n_events))

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

        print("  [{0}] all={1}, events={2}".format(label, len(all_min_voltages), event_count))

    print("Analysis complete.")
    return results


def compute_trigger_rate(time_num, trig_num, event_size):
    """
    Compute trigger rate information.

    MATLAB original:
      time_diff(:,i) = time_num(:,i) - time_num(:,1);
      trig_diff(:,i) = trig_num(:,i) - trig_num(:,1);
      trig_err1 = sum(trig_diff);  trig_err2 = sum(trig_err1);
      Trigger_rate = 4096*file_i/(time_num(4096,1)*4/1000/1000/1000);
    """
    # Time difference (relative to channel 0)
    time_diff = time_num.astype(np.int64) - time_num[:, 0:1].astype(np.int64)
    time_err = np.sum(time_diff)

    # Trigger count difference
    trig_diff = trig_num.astype(np.int64) - trig_num[:, 0:1].astype(np.int64)
    trig_err1 = np.sum(trig_diff, axis=0)  # sum per channel
    trig_err2 = np.sum(trig_err1)

    # Trigger rate: based on the last event's timestamp
    # MATLAB: Trigger_rate = 4096*file_i/(time_num(4096,1)*4/1000/1000/1000)
    # time_num unit is 4ns ticks (250 MHz clock)
    last_ev = min(event_size, 4096) - 1
    if last_ev >= 0 and time_num[last_ev, 0] > 0:
        time_seconds = time_num[last_ev, 0] * 4e-9  # 4ns per tick
        trigger_rate_hz = event_size / time_seconds if time_seconds > 0 else 0
        trigger_rate_khz = trigger_rate_hz / 1000.0
    else:
        trigger_rate_hz = 0
        trigger_rate_khz = 0

    # Total trigger count per channel
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
    Plot trigger rate charts:
      - Total trigger count per channel
      - Sum of trigger count differences (trig_err1)
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: total trigger count per channel
    axes[0].bar(range(64), rate_info['trig_sum_per_channel'])
    axes[0].set_title('Total Trigger Count per Channel')
    axes[0].set_xlabel('Channel (0-63)')
    axes[0].set_ylabel('Total Trigger Count')
    axes[0].set_yscale('log')

    # Right: trig_err1 (sum of trigger count differences)
    axes[1].bar(range(64), rate_info['trig_err1'])
    axes[1].set_title('Sum of Trigger Count Differences (trig_err1)')
    axes[1].set_xlabel('Channel (0-63)')
    axes[1].set_ylabel('Sum of Differences')
    axes[1].axhline(y=0, color='r', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure_trigger_rate.png')
    fig.savefig(outpath, dpi=dpi)
    plt.close(fig)
    print("Saved {0}".format(outpath))

def plot_histograms(results, cfg, output_dir):
    """
    Plot histograms.
    Each channel has 4 subplots: all_voltages, all_indices, event_voltages, event_indices
    Dynamic layout: n_channels rows x 4 columns
    """
    channels = list(results.keys())  # preserve order
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
            (r['all_min_voltages'],
             '{0} Min Voltages (all <{1})'.format(label, cfg['all_threshold']),
             'Voltage'),
            (r['all_min_indices'],
             '{0} Min Indices (all <{1})'.format(label, cfg['all_threshold']),
             'Index'),
            (r['event_voltages'],
             '{0} Min Voltages (event <{1})'.format(label, cfg['event_threshold']),
             'Voltage'),
            (r['event_indices'],
             '{0} Min Indices (event <{1})'.format(label, cfg['event_threshold']),
             'Index'),
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
    print("Saved {0}".format(outpath))


def plot_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir):
    """
    Waveform overlay plot: one subplot per channel, overlay first N events.
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
                   label='Threshold={0}'.format(trigger_threshold[board_idx, ch_idx]))
        ax.set_title('Board {0}, Channel {1} ({2})'.format(board_idx + 1, ch_idx + 1, label))
        ax.set_xlabel('Sample')
        ax.set_ylabel('ADC Value')
        ax.legend()

    for idx in range(n_channels, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()
    outpath = os.path.join(output_dir, 'figure_waveforms_overlay.png')
    fig.savefig(outpath, dpi=dpi)
    plt.close(fig)
    print("Saved {0}".format(outpath))


def plot_single_event_waveforms(data_all, trigger_threshold, event_size, channels, cfg, output_dir):
    """
    Plot waveforms per event: one figure per event, one subplot per channel.
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
            ax.set_title('Event {0}, {1}'.format(ev, label))
            ax.set_xlabel('Sample')
            ax.set_ylabel('ADC Value')

        for idx in range(n_channels, len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        outpath = os.path.join(output_dir, 'event_{0:04d}_waveforms.png'.format(ev))
        fig.savefig(outpath, dpi=dpi)
        plt.close(fig)

        if (ev + 1) % 10 == 0:
            print("  Saved {0}/{1} event waveform plots".format(ev + 1, max_events))

    print("Saved {0} event waveform plots to {1}/".format(max_events, output_dir))


# ============================================================
# Main
# ============================================================

def main():
    # Parse command line arguments manually (compatible with Python 2.7+)
    args = sys.argv[1:]
    input_file = None
    config_file = None
    output_dir = None

    i = 0
    while i < len(args):
        if args[i] in ('-c', '--config') and i + 1 < len(args):
            config_file = args[i + 1]
            i += 2
        elif args[i] in ('-o', '--output') and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] in ('-h', '--help'):
            print("Usage: python file_all.py <input.bin> [-c config.txt] [-o output_dir]")
            print("  input.bin  - PDS1500 binary data file (uint16 LE)")
            print("  -c config.txt  - Configuration file (default: config.txt)")
            print("  -o output_dir  - Output directory (overrides config)")
            sys.exit(0)
        elif not input_file:
            input_file = args[i]
            i += 1
        else:
            i += 1

    if not input_file:
        print("Error: no input file specified.")
        print("Usage: python file_all.py <input.bin> [-c config.txt] [-o output_dir]")
        sys.exit(1)

    # ---- Load config ----
    cfg = load_txt_config(config_file)

    # Parse channels
    channels = parse_channels(cfg)
    if not channels:
        print("Error: no analysis channels specified in config.")
        print("  Add 'analysis_channels = B1C1, B1C7' to config.txt")
        sys.exit(1)

    print("Configured channels:")
    for _, _, label in channels:
        print("  - {0}".format(label))

    # Output directory: command line > config file > default
    output_dir = output_dir or cfg.get('output_dir', './output')
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    print("=" * 50)
    print("  PDS1500 Analysis (Python version)")
    print("  Input:  {0}".format(input_file))
    print("  Output: {0}".format(output_dir))
    print("=" * 50)

    t_start = time.time()

    # ---- Step 1: Read binary file ----
    print("\n[1/7] Reading binary file...")
    data = read_binary(input_file)

    # ---- Step 2: Separate boards ----
    print("[2/7] Separating boards...")
    board_data, event_size = separate_boards(data)
    del data

    # ---- Step 3: Extract trigger thresholds ----
    print("[3/7] Extracting trigger thresholds...")
    trigger_threshold = extract_trigger_threshold(board_data)

    # ---- Step 4: Extract timestamps & trigger counts ----
    print("[4/7] Extracting timestamps and trigger counts...")
    time_num = extract_timestamps(board_data, event_size)
    trig_num = extract_triggers(board_data, event_size)

    # ---- Step 5: Compute trigger rates ----
    print("[5/7] Computing trigger rates...")
    rate_info = compute_trigger_rate(time_num, trig_num, event_size)

    # ---- Step 6: Extract waveform data ----
    print("[6/7] Extracting waveform data...")
    data_all = extract_waveform(board_data, event_size)
    del board_data

    # ---- Step 7: Analyze channels ----
    print("[7/7] Analyzing channels...")
    results = analyze_channels(data_all, event_size, channels, cfg)

    # ---- Generate plots ----
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

    # ---- Summary ----
    t_end = time.time()

    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)
    print("  Total events:              {0}".format(event_size))
    print("  Thresholds:                all={0}, event={1}".format(
        cfg['all_threshold'], cfg['event_threshold']))
    for label in results:
        r = results[label]
        rate = r['event_count'] / float(event_size)
        print("  {0}: events(<{1})={2}, rate={3:.6f}, all(<{4})={5}".format(
            label, cfg['event_threshold'], r['event_count'],
            rate, cfg['all_threshold'], r['all_count']))
    print("  --- Trigger Rate ---")
    print("  System trigger rate:       {0:.2f} Hz ({1:.3f} kHz)".format(
        rate_info['trigger_rate_hz'], rate_info['trigger_rate_khz']))
    print("  Time error (sum time_diff): {0}".format(rate_info['time_err']))
    print("  Trig error1 range:         [{0}, {1}]".format(
        np.min(rate_info['trig_err1']), np.max(rate_info['trig_err1'])))
    print("  Trig error2 (total sum):   {0}".format(rate_info['trig_err2']))
    print("  Elapsed time:              {0:.2f} seconds".format(t_end - t_start))
    print("\n  Output saved to: {0}/".format(output_dir))
    print("Done.")


if __name__ == '__main__':
    main()
