"""
pds1500_reader.py - PDS1500 binary data reader and decoder module.

Responsible for:
  1. Reading uint16 LE binary files
  2. Separating data by 8 boards x 8 channels
  3. Extracting trigger thresholds
  4. Extracting timestamps
  5. Extracting trigger counts
  6. Extracting waveform data

Data format (per event = 65536 samples):
  - 8 boards, each board 8192 samples
  - Each board has 8 channels, each channel 1024 samples
  - Per channel 1024 samples layout:
      [0:8]     header
      [8:1008]  waveform data (1000 samples)
      [1008:1012] timestamp (4 x uint16 -> 64-bit)
      [1012:1016] trigger count (4 x uint16 -> 64-bit)
      [1016]    trigger threshold
      [1017:1024] trailer
"""

import numpy as np


# ============================================================
# Constants
# ============================================================
BOARD_NUM = 8
CHANNEL_NUM = 8
SAMPLES_PER_BOARD = 8192       # samples per board per event
SAMPLES_PER_CHANNEL = 1024     # samples per channel per event
WAVEFORM_LEN = 1000            # waveform data length
TOTAL_PER_EVENT = BOARD_NUM * SAMPLES_PER_BOARD  # 65536


def read_binary(filename):
    """
    Read uint16 little-endian binary file.

    Args:
        filename: path to binary file

    Returns:
        data: 1-D numpy array (dtype=uint16)
    """
    data = np.fromfile(filename, dtype=np.uint16)
    print("Read {0} samples from {1}".format(len(data), filename))
    return data


def separate_boards(data):
    """
    Separate data by boards.

    Each event = 65536 samples = 8 boards x 8192 samples/board.
    Data is arranged consecutively by events, within each event by board order.

    Args:
        data: 1-D numpy array, raw uint16 data

    Returns:
        board_data: list of 8 arrays, each shape = (event_size, 8192)
        event_size: int, number of events
    """
    data_end = len(data)
    data_size = data_end // CHANNEL_NUM           # total data per board
    event_size = data_size // SAMPLES_PER_BOARD    # number of events
    print("data_size={0}, event_size={1}".format(data_size, event_size))

    # Trim to complete events, reshape to (event_size, 65536)
    usable = event_size * TOTAL_PER_EVENT
    data_trimmed = data[:usable].reshape(event_size, TOTAL_PER_EVENT)

    # Split into 8 boards: each shape = (event_size, 8192)
    board_data = []
    for b in range(BOARD_NUM):
        bd = data_trimmed[:, b * SAMPLES_PER_BOARD : (b + 1) * SAMPLES_PER_BOARD]
        board_data.append(bd)

    print("Board separation complete.")
    return board_data, event_size


def extract_trigger_threshold(board_data):
    """
    Extract trigger thresholds.

    Each channel's 1017th sample (MATLAB 1-indexed -> Python index 1016).

    Args:
        board_data: list of (event_size, 8192) arrays

    Returns:
        trigger_threshold: (8, 8) ndarray, dtype=uint16
    """
    trigger_threshold = np.zeros((BOARD_NUM, CHANNEL_NUM), dtype=np.uint16)
    for b in range(BOARD_NUM):
        for c in range(CHANNEL_NUM):
            # MATLAB: 1024*(i-1)+1017 -> Python: 1024*c + 1016
            trigger_threshold[b, c] = board_data[b][0, 1024 * c + 1016]
    print("Trigger thresholds extracted.")
    return trigger_threshold


def extract_timestamps(board_data, event_size):
    """
    Extract timestamps.

    MATLAB original logic:
      time_num = v0*16^0 + v1*16^4 + v2*16^8 + v3*16^12
    i.e.: v0 + v1*65536 + v2*65536^2 + v3*65536^3

    Timestamps are at sample 1009-1012 of each channel (MATLAB 1-indexed).

    Args:
        board_data: list of (event_size, 8192) arrays
        event_size: number of events

    Returns:
        time_num: (event_size, 64) ndarray, dtype=uint64
                  64 = 8 boards x 8 channels
    """
    time_num = np.zeros((event_size, 64), dtype=np.uint64)

    for c in range(CHANNEL_NUM):
        base = 1024 * c
        # MATLAB 1-indexed: 1009,1010,1011,1012 -> Python: 1008,1009,1010,1011
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
    Extract trigger counts.

    Trigger counts are at sample 1013-1016 of each channel (MATLAB 1-indexed).

    Args:
        board_data: list of (event_size, 8192) arrays
        event_size: number of events

    Returns:
        trig_num: (event_size, 64) ndarray, dtype=uint64
    """
    trig_num = np.zeros((event_size, 64), dtype=np.uint64)

    for c in range(CHANNEL_NUM):
        base = 1024 * c
        # MATLAB 1-indexed: 1013,1014,1015,1016 -> Python: 1012,1013,1014,1015
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
    Extract waveform data.

    Waveform data is at sample 9-1008 of each channel (MATLAB 1-indexed),
    total 1000 samples.

    Args:
        board_data: list of (event_size, 8192) arrays
        event_size: number of events

    Returns:
        data_all: (event_size, BOARD_NUM, CHANNEL_NUM, WAVEFORM_LEN) ndarray, dtype=uint16
    """
    data_all = np.zeros((event_size, BOARD_NUM, CHANNEL_NUM, WAVEFORM_LEN), dtype=np.uint16)

    for b in range(BOARD_NUM):
        for c in range(CHANNEL_NUM):
            base = 1024 * c
            start = base + 8       # MATLAB +9 (1-indexed)
            end = base + 1008      # MATLAB +1008 inclusive -> Python :1008 exclusive
            data_all[:, b, c, :] = board_data[b][:, start:end]

    print("Waveform data extracted.")
    return data_all


def load_pds1500_file(filename):
    """
    One-stop loading of PDS1500 data file, returns all extracted results.

    Args:
        filename: path to binary file

    Returns:
        dict containing:
            'board_data':        list of 8 arrays
            'event_size':        int
            'trigger_threshold': (8,8) ndarray
            'time_num':          (event_size, 64) ndarray
            'trig_num':          (event_size, 64) ndarray
            'data_all':          (event_size, 8, 8, 1000) ndarray
    """
    print("\nLoading PDS1500 file: {0}".format(filename))
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
