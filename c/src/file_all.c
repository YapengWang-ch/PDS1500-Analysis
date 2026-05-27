#include "file_all.h"

/* 初始化数据结构 */
FileAllData* file_all_init(void) {
    FileAllData *fd = (FileAllData*)calloc(1, sizeof(FileAllData));
    if (!fd) {
        fprintf(stderr, "Error: failed to allocate FileAllData\n");
        return NULL;
    }
    return fd;
}

/* 释放所有内存 */
void file_all_free(FileAllData *fd) {
    if (!fd) return;
    
    free(fd->data);
    
    for (int b = 0; b < BOARD_NUM; b++) {
        free(fd->board_data[b]);
        if (fd->board_split[b]) {
            for (size_t e = 0; e < fd->event_size; e++) {
                free(fd->board_split[b][e]);
            }
            free(fd->board_split[b]);
        }
    }
    
    if (fd->time_num) {
        for (size_t e = 0; e < fd->event_size; e++) free(fd->time_num[e]);
        free(fd->time_num);
    }
    if (fd->trig_num) {
        for (size_t e = 0; e < fd->event_size; e++) free(fd->trig_num[e]);
        free(fd->trig_num);
    }
    
    if (fd->data_all) {
        for (size_t e = 0; e < fd->event_size; e++) {
            if (fd->data_all[e]) {
                for (int b = 0; b < BOARD_NUM; b++) {
                    if (fd->data_all[e][b]) {
                        for (int c = 0; c < CHANNEL_NUM; c++) {
                            free(fd->data_all[e][b][c]);
                        }
                        free(fd->data_all[e][b]);
                    }
                }
                free(fd->data_all[e]);
            }
        }
        free(fd->data_all);
    }
    
    free(fd->all_min_voltages_ch1);
    free(fd->all_min_indices_ch1);
    free(fd->all_min_voltages_ch7);
    free(fd->all_min_indices_ch7);
    free(fd->event_voltages_ch1);
    free(fd->event_indices_ch1);
    free(fd->event_voltages_ch7);
    free(fd->event_indices_ch7);
    
    free(fd);
}

/* 读取二进制文件 (uint16 little-endian) */
int file_all_read_binary(FileAllData *fd, const char *filename) {
    FILE *fp = fopen(filename, "rb");
    if (!fp) {
        fprintf(stderr, "Error: cannot open file %s\n", filename);
        return -1;
    }
    
    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    rewind(fp);
    
    fd->data_len = file_size / sizeof(uint16_t);
    fd->data = (uint16_t*)malloc(file_size);
    if (!fd->data) {
        fprintf(stderr, "Error: memory allocation failed\n");
        fclose(fp);
        return -1;
    }
    
    size_t read_count = fread(fd->data, sizeof(uint16_t), fd->data_len, fp);
    fclose(fp);
    
    if (read_count != fd->data_len) {
        fprintf(stderr, "Warning: read %zu / %zu samples\n", read_count, fd->data_len);
        fd->data_len = read_count;
    }
    
    printf("Read %zu samples from %s\n", fd->data_len, filename);
    return 0;
}

/* 按板子分离数据 */
int file_all_separate_boards(FileAllData *fd) {
    size_t data_end = fd->data_len;
    size_t data_size = (data_end / CHANNEL_NUM);  /* 每个板子的数据量 */
    fd->event_size = data_size / SAMPLES_PER_BOARD;
    
    if (fd->event_size > EVENT_SIZE_MAX) {
        fprintf(stderr, "Warning: event_size %zu exceeds max %d, truncating\n",
                fd->event_size, EVENT_SIZE_MAX);
        fd->event_size = EVENT_SIZE_MAX;
    }
    
    printf("data_size=%zu, event_size=%zu\n", data_size, fd->event_size);
    
    /* 为每个板子分配内存 */
    for (int b = 0; b < BOARD_NUM; b++) {
        fd->board_data[b] = (uint16_t*)calloc(data_size, sizeof(uint16_t));
        if (!fd->board_data[b]) {
            fprintf(stderr, "Error: memory allocation for board %d\n", b);
            return -1;
        }
    }
    
    /* 分离数据: 每个事件65536个sample, 每个板子8192个sample */
    for (size_t ev = 0; ev < fd->event_size; ev++) {
        size_t ev_offset = ev * 65536;  /* 65536 = 8 boards * 8192 samples */
        
        for (int b = 0; b < BOARD_NUM; b++) {
            size_t board_offset = ev_offset + b * SAMPLES_PER_BOARD;
            size_t dest_offset = ev * SAMPLES_PER_BOARD;
            
            memcpy(fd->board_data[b] + dest_offset,
                   fd->data + board_offset,
                   SAMPLES_PER_BOARD * sizeof(uint16_t));
        }
    }
    
    printf("Board separation complete.\n");
    return 0;
}

/* 按事件拆分每个板子的数据 */
int file_all_separate_events(FileAllData *fd) {
    for (int b = 0; b < BOARD_NUM; b++) {
        fd->board_split[b] = (uint16_t**)malloc(fd->event_size * sizeof(uint16_t*));
        if (!fd->board_split[b]) {
            fprintf(stderr, "Error: memory allocation for board_split[%d]\n", b);
            return -1;
        }
        
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            fd->board_split[b][ev] = (uint16_t*)malloc(SAMPLES_PER_BOARD * sizeof(uint16_t));
            if (!fd->board_split[b][ev]) {
                fprintf(stderr, "Error: memory allocation for board_split[%d][%zu]\n", b, ev);
                return -1;
            }
            memcpy(fd->board_split[b][ev],
                   fd->board_data[b] + ev * SAMPLES_PER_BOARD,
                   SAMPLES_PER_BOARD * sizeof(uint16_t));
        }
    }
    
    printf("Event separation complete.\n");
    return 0;
}

/* 提取触发阈值 (每个channel的第1017个sample, 1-indexed -> index 1016) */
int file_all_extract_trigger_threshold(FileAllData *fd) {
    for (int b = 0; b < BOARD_NUM; b++) {
        for (int c = 0; c < CHANNEL_NUM; c++) {
            /* MATLAB: 1024*(i-1)+1017, 1-indexed => C: 1024*c + 1016 */
            fd->trigger_threshold[b][c] = fd->board_split[b][0][1024 * c + 1016];
        }
    }
    
    printf("Trigger thresholds extracted.\n");
    return 0;
}

/* 提取时间戳 */
int file_all_extract_timestamps(FileAllData *fd) {
    fd->time_num = (uint32_t**)malloc(fd->event_size * sizeof(uint32_t*));
    if (!fd->time_num) return -1;
    
    for (size_t ev = 0; ev < fd->event_size; ev++) {
        fd->time_num[ev] = (uint32_t*)calloc(64, sizeof(uint32_t));
        if (!fd->time_num[ev]) return -1;
    }
    
    for (int c = 0; c < CHANNEL_NUM; c++) {
        /* 每个channel内的偏移: 1009,1010,1011,1012 (1-indexed) => 1008,1009,1010,1011 */
        int base = 1024 * c;
        int t0 = base + 1008;
        int t1 = base + 1009;
        int t2 = base + 1010;
        int t3 = base + 1011;
        
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            for (int b = 0; b < BOARD_NUM; b++) {
                uint32_t val = (uint32_t)fd->board_split[b][ev][t0] * 1
                             + (uint32_t)fd->board_split[b][ev][t1] * 4096    /* 16^3? No, MATLAB uses 16^4 */
                             + (uint32_t)fd->board_split[b][ev][t2] * 16777216 /* 16^8? No */
                             + (uint32_t)fd->board_split[b][ev][t3] * 68719476736ULL; /* 16^12 */
                /* 修正: MATLAB用 16^0, 16^4, 16^8, 16^12 */
                /* 实际上 uint16 每个值最大65535, 16^4=65536, 所以每个sample贡献不同位 */
                /* 这里简化: 直接用位移 */
                val = (uint32_t)fd->board_split[b][ev][t0]
                    | ((uint32_t)fd->board_split[b][ev][t1] << 16);
                /* 高位部分 */
                uint32_t val_high = (uint32_t)fd->board_split[b][ev][t2]
                                  | ((uint32_t)fd->board_split[b][ev][t3] << 16);
                
                fd->time_num[ev][b * 8 + c] = val | (val_high << 32);
                /* 实际上MATLAB的16^0,16^4,16^8,16^12意味着每4个hex digit */
                /* 但uint16只有4个hex digit, 所以每个值就是16^0项 */
                /* 重新理解: data是uint16, dec2hex后每个值变成4位hex字符串 */
                /* 然后拼接: 值0*16^0 + 值1*16^4 + 值2*16^8 + 值3*16^12 */
                /* 即: val0 + val1*65536 + val2*65536^2 + val3*65536^3 */
            }
        }
    }
    
    /* 修正版本: 正确理解MATLAB的运算 */
    for (int c = 0; c < CHANNEL_NUM; c++) {
        int base = 1024 * c;
        int t0 = base + 1008;  /* 1009 in 1-indexed */
        int t1 = base + 1009;  /* 1010 */
        int t2 = base + 1010;  /* 1011 */
        int t3 = base + 1011;  /* 1012 */
        
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            for (int b = 0; b < BOARD_NUM; b++) {
                uint64_t v0 = fd->board_split[b][ev][t0];
                uint64_t v1 = fd->board_split[b][ev][t1];
                uint64_t v2 = fd->board_split[b][ev][t2];
                uint64_t v3 = fd->board_split[b][ev][t3];
                
                /* MATLAB: v0*16^0 + v1*16^4 + v2*16^8 + v3*16^12 */
                fd->time_num[ev][b * 8 + c] = (uint32_t)(
                    v0 + v1 * 65536ULL + v2 * 4294967296ULL + v3 * 281474976710656ULL
                );
            }
        }
    }
    
    printf("Timestamps extracted.\n");
    return 0;
}

/* 提取触发计数 */
int file_all_extract_triggers(FileAllData *fd) {
    fd->trig_num = (uint32_t**)malloc(fd->event_size * sizeof(uint32_t*));
    if (!fd->trig_num) return -1;
    
    for (size_t ev = 0; ev < fd->event_size; ev++) {
        fd->trig_num[ev] = (uint32_t*)calloc(64, sizeof(uint32_t));
        if (!fd->trig_num[ev]) return -1;
    }
    
    for (int c = 0; c < CHANNEL_NUM; c++) {
        int base = 1024 * c;
        /* MATLAB: 1013,1014,1015,1016 (1-indexed) => 1012,1013,1014,1015 */
        int t0 = base + 1012;
        int t1 = base + 1013;
        int t2 = base + 1014;
        int t3 = base + 1015;
        
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            for (int b = 0; b < BOARD_NUM; b++) {
                uint64_t v0 = fd->board_split[b][ev][t0];
                uint64_t v1 = fd->board_split[b][ev][t1];
                uint64_t v2 = fd->board_split[b][ev][t2];
                uint64_t v3 = fd->board_split[b][ev][t3];
                
                fd->trig_num[ev][b * 8 + c] = (uint32_t)(
                    v0 + v1 * 65536ULL + v2 * 4294967296ULL + v3 * 281474976710656ULL
                );
            }
        }
    }
    
    printf("Trigger counts extracted.\n");
    return 0;
}

/* 提取波形数据: data_all[event][board][channel][1000] */
int file_all_extract_waveform(FileAllData *fd) {
    fd->data_all = (uint16_t****)malloc(fd->event_size * sizeof(uint16_t***));
    if (!fd->data_all) return -1;
    
    for (size_t ev = 0; ev < fd->event_size; ev++) {
        fd->data_all[ev] = (uint16_t***)malloc(BOARD_NUM * sizeof(uint16_t**));
        if (!fd->data_all[ev]) return -1;
        
        for (int b = 0; b < BOARD_NUM; b++) {
            fd->data_all[ev][b] = (uint16_t**)malloc(CHANNEL_NUM * sizeof(uint16_t*));
            if (!fd->data_all[ev][b]) return -1;
            
            for (int c = 0; c < CHANNEL_NUM; c++) {
                fd->data_all[ev][b][c] = (uint16_t*)malloc(WAVEFORM_LEN * sizeof(uint16_t));
                if (!fd->data_all[ev][b][c]) return -1;
                
                /* MATLAB: 1024*(i-1)+9 : 1024*(i-1)+1008 (1-indexed) */
                /* C: 1024*c+8 : 1024*c+1007 */
                int base = 1024 * c;
                for (int s = 0; s < WAVEFORM_LEN; s++) {
                    fd->data_all[ev][b][c][s] = fd->board_split[b][ev][base + 8 + s];
                }
            }
        }
    }
    
    printf("Waveform data extracted.\n");
    return 0;
}

/* 分析channel 1和channel 7 */
int file_all_analyze_channels(FileAllData *fd) {
    size_t max_results = fd->event_size;
    
    /* 分配结果数组 */
    fd->all_min_voltages_ch1 = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->all_min_indices_ch1  = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->all_min_voltages_ch7 = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->all_min_indices_ch7  = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    
    fd->event_voltages_ch1 = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->event_indices_ch1  = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->event_voltages_ch7 = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    fd->event_indices_ch7  = (uint16_t*)malloc(max_results * sizeof(uint16_t));
    
    fd->all_count_ch1 = 0;
    fd->all_count_ch7 = 0;
    fd->event_count_ch1 = 0;
    fd->event_count_ch7 = 0;
    
    uint16_t threshold_all = 14900;
    uint16_t threshold_event = 14820;
    
    for (size_t ev = 0; ev < fd->event_size; ev++) {
        int board_id = 0;  /* 只分析board 1 (index 0) */
        
        /* Channel 1 (index 0) */
        {
            uint16_t *waveform = fd->data_all[ev][board_id][0];
            uint16_t min_val = waveform[0];
            uint16_t min_idx = 0;
            
            for (int s = 1; s < WAVEFORM_LEN; s++) {
                if (waveform[s] < min_val) {
                    min_val = waveform[s];
                    min_idx = (uint16_t)s;
                }
            }
            
            if (min_val < threshold_all) {
                fd->all_min_voltages_ch1[fd->all_count_ch1] = min_val;
                fd->all_min_indices_ch1[fd->all_count_ch1] = min_idx;
                fd->all_count_ch1++;
            }
            
            if (min_val < threshold_event) {
                fd->event_voltages_ch1[fd->event_count_ch1] = min_val;
                fd->event_indices_ch1[fd->event_count_ch1] = min_idx;
                fd->event_count_ch1++;
            }
        }
        
        /* Channel 7 (index 6) */
        {
            uint16_t *waveform = fd->data_all[ev][board_id][6];
            uint16_t min_val = waveform[0];
            uint16_t min_idx = 0;
            
            for (int s = 1; s < WAVEFORM_LEN; s++) {
                if (waveform[s] < min_val) {
                    min_val = waveform[s];
                    min_idx = (uint16_t)s;
                }
            }
            
            if (min_val < threshold_all) {
                fd->all_min_voltages_ch7[fd->all_count_ch7] = min_val;
                fd->all_min_indices_ch7[fd->all_count_ch7] = min_idx;
                fd->all_count_ch7++;
            }
            
            if (min_val < threshold_event) {
                fd->event_voltages_ch7[fd->event_count_ch7] = min_val;
                fd->event_indices_ch7[fd->event_count_ch7] = min_idx;
                fd->event_count_ch7++;
            }
        }
        
        if ((ev + 1) % 100 == 0) {
            printf("Processed event %zu / %zu\n", ev + 1, fd->event_size);
        }
    }
    
    printf("Analysis complete.\n");
    printf("CH1: all=%zu, events=%zu\n", fd->all_count_ch1, fd->event_count_ch1);
    printf("CH7: all=%zu, events=%zu\n", fd->all_count_ch7, fd->event_count_ch7);
    
    return 0;
}

/* 写入结果到文件 */
int file_all_write_results(FileAllData *fd, const char *outdir) {
    char fname[512];
    FILE *fp;
    
    /* 创建输出目录 */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "mkdir -p %s", outdir);
    system(cmd);
    
    /* 写入触发阈值 */
    snprintf(fname, sizeof(fname), "%s/trigger_threshold.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# Board Channel Threshold\n");
        for (int b = 0; b < BOARD_NUM; b++) {
            for (int c = 0; c < CHANNEL_NUM; c++) {
                fprintf(fp, "%d %d %u\n", b + 1, c + 1, fd->trigger_threshold[b][c]);
            }
        }
        fclose(fp);
    }
    
    /* 写入时间戳 */
    snprintf(fname, sizeof(fname), "%s/time_num.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# Event Channel(0-63) Timestamp\n");
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            for (int ch = 0; ch < 64; ch++) {
                fprintf(fp, "%zu %d %u\n", ev, ch, fd->time_num[ev][ch]);
            }
        }
        fclose(fp);
    }
    
    /* 写入触发计数 */
    snprintf(fname, sizeof(fname), "%s/trig_num.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# Event Channel(0-63) TriggerCount\n");
        for (size_t ev = 0; ev < fd->event_size; ev++) {
            for (int ch = 0; ch < 64; ch++) {
                fprintf(fp, "%zu %d %u\n", ev, ch, fd->trig_num[ev][ch]);
            }
        }
        fclose(fp);
    }
    
    /* 写入波形数据 */
    snprintf(fname, sizeof(fname), "%s/waveform.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# Event Board Channel Sample[0-%d] Value\n", WAVEFORM_LEN - 1);
        for (size_t ev = 0; ev < fd->event_size && ev < 200; ev++) {
            for (int b = 0; b < BOARD_NUM; b++) {
                for (int c = 0; c < CHANNEL_NUM; c++) {
                    for (int s = 0; s < WAVEFORM_LEN; s++) {
                        fprintf(fp, "%zu %d %d %d %u\n",
                                ev, b + 1, c + 1, s,
                                fd->data_all[ev][b][c][s]);
                    }
                }
            }
        }
        fclose(fp);
    }
    
    /* 写入分析结果 */
    snprintf(fname, sizeof(fname), "%s/analysis_ch1_all.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# MinVoltage MinIndex\n");
        for (size_t i = 0; i < fd->all_count_ch1; i++) {
            fprintf(fp, "%u %u\n", fd->all_min_voltages_ch1[i], fd->all_min_indices_ch1[i]);
        }
        fclose(fp);
    }
    
    snprintf(fname, sizeof(fname), "%s/analysis_ch7_all.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# MinVoltage MinIndex\n");
        for (size_t i = 0; i < fd->all_count_ch7; i++) {
            fprintf(fp, "%u %u\n", fd->all_min_voltages_ch7[i], fd->all_min_indices_ch7[i]);
        }
        fclose(fp);
    }
    
    snprintf(fname, sizeof(fname), "%s/analysis_ch1_event.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# MinVoltage MinIndex\n");
        for (size_t i = 0; i < fd->event_count_ch1; i++) {
            fprintf(fp, "%u %u\n", fd->event_voltages_ch1[i], fd->event_indices_ch1[i]);
        }
        fclose(fp);
    }
    
    snprintf(fname, sizeof(fname), "%s/analysis_ch7_event.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "# MinVoltage MinIndex\n");
        for (size_t i = 0; i < fd->event_count_ch7; i++) {
            fprintf(fp, "%u %u\n", fd->event_voltages_ch7[i], fd->event_indices_ch7[i]);
        }
        fclose(fp);
    }
    
    /* 写入汇总统计 */
    snprintf(fname, sizeof(fname), "%s/summary.txt", outdir);
    fp = fopen(fname, "w");
    if (fp) {
        fprintf(fp, "Total events: %zu\n", fd->event_size);
        fprintf(fp, "CH1 threshold: 14820\n");
        fprintf(fp, "CH7 threshold: 14820\n");
        fprintf(fp, "CH1 all counts (<14900): %zu\n", fd->all_count_ch1);
        fprintf(fp, "CH7 all counts (<14900): %zu\n", fd->all_count_ch7);
        fprintf(fp, "CH1 event counts (<14820): %zu\n", fd->event_count_ch1);
        fprintf(fp, "CH7 event counts (<14820): %zu\n", fd->event_count_ch7);
        
        double rate_ch1 = (double)fd->event_count_ch1 / fd->event_size;
        double rate_ch7 = (double)fd->event_count_ch7 / fd->event_size;
        fprintf(fp, "CH1 rate: %f\n", rate_ch1);
        fprintf(fp, "CH7 rate: %f\n", rate_ch7);
        fclose(fp);
    }
    
    printf("Results written to %s/\n", outdir);
    return 0;
}
