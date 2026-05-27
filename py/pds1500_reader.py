"""
pds1500_reader.py — PDS1500 二进制数据读取与解码模块

负责:
  1. 读取 uint16 LE 二进制文件
  2. 按 8 板 × 8 通道分离数据
  3. 提取触发阈值
  4. 提取时间戳
  5. 提取触发计数
  6. 提取波形数据

数据格式 (每事件 = 65536 samples):
  - 8 个板子 (board), 每个板子 8192 samples
  - 每个板子 8 个通道 (channel), 每个通道 1024 samples
  - 每通道 1024 samples 中:
      [0:8]     header
      [8:1008]  波形数据 (1000 samples)
      [1008:1012] 时间戳 (4 × uint16 → 64-bit)
      [1012:1016] 触发计数 (4 × uint16 → 64-bit)
      [1016]    触发阈值
      [1017:1024] trailer
"""

import numpy as np


# ============================================================
# 常量
# ============================================================
BOARD_NUM = 8
CHANNEL_NUM = 8
SAMPLES_PER_BOARD = 8192       # 每板每事件的采样点数
SAMPLES_PER_CHANNEL = 1024     # 每通道每事件的采样点数
WAVEFORM_LEN = 1000            # 波形数据长度
TOTAL_PER_EVENT = BOARD_NUM * SAMPLES_PER_BOARD  # 65536


def read_binary(filename):
    """
    读取 uint16 little-endian 二进制文件.
    
    参数:
      filename: 二进制文件路径
    
    返回:
      data: 1-D numpy array (dtype=uint16)
    """
    data = np.fromfile(filename, dtype=np.uint16)
    print(f"Read {len(data)} samples from {filename}")
    return data


def separate_boards(data):
    """
    按板子分离数据.
    
    每个事件 = 65536 samples = 8 boards × 8192 samples/board.
    数据在文件中按事件连续排列, 每个事件内按板子顺序排列.
    
    参数:
      data: 1-D numpy array, 原始 uint16 数据
    
    返回:
      board_data: list of 8 arrays, 每个 shape = (event_size, 8192)
      event_size: int, 事件数
    """
    data_end = len(data)
    data_size = data_end // CHANNEL_NUM           # 每个板子的总数据量
    event_size = data_size // SAMPLES_PER_BOARD    # 事件数
    print(f"data_size={data_size}, event_size={event_size}")

    # 截取完整事件部分, reshape 为 (event_size, 65536)
    usable = event_size * TOTAL_PER_EVENT
    data_trimmed = data[:usable].reshape(event_size, TOTAL_PER_EVENT)

    # 拆分为 8 个板子: 每个 shape = (event_size, 8192)
    board_data = []
    for b in range(BOARD_NUM):
        bd = data_trimmed[:, b * SAMPLES_PER_BOARD : (b + 1) * SAMPLES_PER_BOARD]
        board_data.append(bd)

    print("Board separation complete.")
    return board_data, event_size


def extract_trigger_threshold(board_data):
    """
    提取触发阈值.
    
    每个 channel 的第 1017 个 sample (MATLAB 1-indexed → Python index 1016)
    
    参数:
      board_data: list of (event_size, 8192) arrays
    
    返回:
      trigger_threshold: (8, 8) ndarray, dtype=uint16
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
    
    MATLAB 原版逻辑:
      time_num = v0*16^0 + v1*16^4 + v2*16^8 + v3*16^12
    即: v0 + v1*65536 + v2*65536^2 + v3*65536^3
    
    时间戳位于每通道的 sample 1009-1012 (MATLAB 1-indexed).
    
    参数:
      board_data: list of (event_size, 8192) arrays
      event_size: 事件数
    
    返回:
      time_num: (event_size, 64) ndarray, dtype=uint64
                64 = 8 boards × 8 channels
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
    
    触发计数位于每通道的 sample 1013-1016 (MATLAB 1-indexed).
    
    参数:
      board_data: list of (event_size, 8192) arrays
      event_size: 事件数
    
    返回:
      trig_num: (event_size, 64) ndarray, dtype=uint64
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
    
    波形数据位于每通道的 sample 9-1008 (MATLAB 1-indexed), 共 1000 个采样点.
    
    参数:
      board_data: list of (event_size, 8192) arrays
      event_size: 事件数
    
    返回:
      data_all: (event_size, BOARD_NUM, CHANNEL_NUM, WAVEFORM_LEN) ndarray, dtype=uint16
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


def load_pds1500_file(filename):
    """
    一站式加载 PDS1500 数据文件, 返回所有提取结果.
    
    参数:
      filename: 二进制文件路径
    
    返回:
      dict 包含:
        'board_data':        list of 8 arrays
        'event_size':        int
        'trigger_threshold': (8,8) ndarray
        'time_num':          (event_size, 64) ndarray
        'trig_num':          (event_size, 64) ndarray
        'data_all':          (event_size, 8, 8, 1000) ndarray
    """
    print(f"\nLoading PDS1500 file: {filename}")
    print("-" * 40)

    data = read_binary(filename)
    board_data, event_size = separate_boards(data)
    del data

    trigger_threshold = extract_trigger_threshold(board_data)
    time_num = extract_timestamps(board_data, event_size)
    trig_num = extract_triggers(board_data, event_size)
    data_all = extract_waveform(board_data, event_size)

    print("-" * 40)
    print("File loaded successfully.\n")

    return {
        'board_data': board_data,
        'event_size': event_size,
        'trigger_threshold': trigger_threshold,
        'time_num': time_num,
        'trig_num': trig_num,
        'data_all': data_all,
    }
