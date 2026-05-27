#ifndef FILE_ALL_H
#define FILE_ALL_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* 常量定义 */
#define BOARD_NUM      8
#define CHANNEL_NUM    8
#define EVENT_SIZE_MAX 4096
#define WAVEFORM_LEN   1000
#define SAMPLES_PER_BOARD 8192
#define BYTES_PER_EVENT (65536 * sizeof(uint16_t))  /* 65536 samples * 2 bytes */

/* 数据结构 */
typedef struct {
    uint16_t *data;           /* 原始数据 */
    size_t   data_len;        /* 数据总长度(samples) */
    size_t   event_size;      /* 事件数 */
    
    /* 8个板子的数据, 每个板子 SAMPLES_PER_BOARD * event_size 个samples */
    uint16_t *board_data[BOARD_NUM];
    
    /* 拆分后的事件数据: [event][sample] */
    uint16_t **board_split[BOARD_NUM];
    
    /* 触发阈值 [board][channel] */
    uint16_t trigger_threshold[BOARD_NUM][CHANNEL_NUM];
    
    /* 时间戳 [event][64] */
    uint32_t **time_num;
    
    /* 触发计数 [event][64] */
    uint32_t **trig_num;
    
    /* 波形数据: data_all[event][board][channel][sample] */
    uint16_t ****data_all;
    
    /* 分析结果 */
    uint16_t *all_min_voltages_ch1;
    uint16_t *all_min_indices_ch1;
    uint16_t *all_min_voltages_ch7;
    uint16_t *all_min_indices_ch7;
    size_t    all_count_ch1;
    size_t    all_count_ch7;
    
    uint16_t *event_voltages_ch1;
    uint16_t *event_indices_ch1;
    uint16_t *event_voltages_ch7;
    uint16_t *event_indices_ch7;
    size_t    event_count_ch1;
    size_t    event_count_ch7;
    
} FileAllData;

/* 函数声明 */
FileAllData* file_all_init(void);
void file_all_free(FileAllData *fd);
int file_all_read_binary(FileAllData *fd, const char *filename);
int file_all_separate_boards(FileAllData *fd);
int file_all_separate_events(FileAllData *fd);
int file_all_extract_trigger_threshold(FileAllData *fd);
int file_all_extract_timestamps(FileAllData *fd);
int file_all_extract_triggers(FileAllData *fd);
int file_all_extract_waveform(FileAllData *fd);
int file_all_analyze_channels(FileAllData *fd);
int file_all_write_results(FileAllData *fd, const char *outdir);

#endif /* FILE_ALL_H */
