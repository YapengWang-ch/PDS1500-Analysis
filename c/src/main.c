/**
 * file_all C 版本 - 主程序入口
 * 
 * 将 MATLAB 的 file_all.m 翻译为 C 语言实现。
 * 
 * 功能:
 *   1. 读取 PDS1500 二进制数据文件 (uint16 LE)
 *   2. 按 8 板 × 8 通道分离数据
 *   3. 提取触发阈值、时间戳、触发计数
 *   4. 提取波形数据 (每通道 1000 个采样点)
 *   5. 分析 Channel 1 和 Channel 7 的最小值
 *   6. 输出结果到文本文件
 * 
 * 用法:
 *   ./pds1500_analysis <input.bin> [output_dir]
 * 
 * 编译:
 *   mkdir build && cd build
 *   cmake ..
 *   make
 */

#include "file_all.h"
#include <time.h>

int main(int argc, char *argv[]) {
    const char *input_file;
    const char *output_dir;
    
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <input.bin> [output_dir]\n", argv[0]);
        fprintf(stderr, "  input.bin  - PDS1500 binary data file\n");
        fprintf(stderr, "  output_dir - output directory (default: ./output)\n");
        return 1;
    }
    
    input_file = argv[1];
    output_dir = (argc >= 3) ? argv[2] : "./output";
    
    printf("=== PDS1500 Analysis (C version) ===\n");
    printf("Input:  %s\n", input_file);
    printf("Output: %s\n\n", output_dir);
    
    clock_t t_start = clock();
    
    /* 初始化 */
    FileAllData *fd = file_all_init();
    if (!fd) {
        fprintf(stderr, "Failed to initialize.\n");
        return 1;
    }
    
    /* 步骤1: 读取二进制文件 */
    printf("[1/8] Reading binary file...\n");
    if (file_all_read_binary(fd, input_file) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤2: 按板子分离数据 */
    printf("[2/8] Separating boards...\n");
    if (file_all_separate_boards(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤3: 按事件拆分 */
    printf("[3/8] Separating events...\n");
    if (file_all_separate_events(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤4: 提取触发阈值 */
    printf("[4/8] Extracting trigger thresholds...\n");
    if (file_all_extract_trigger_threshold(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤5: 提取时间戳 */
    printf("[5/8] Extracting timestamps...\n");
    if (file_all_extract_timestamps(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤6: 提取触发计数 */
    printf("[6/8] Extracting trigger counts...\n");
    if (file_all_extract_triggers(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤7: 提取波形数据 */
    printf("[7/8] Extracting waveform data...\n");
    if (file_all_extract_waveform(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 步骤8: 分析 channel 1 & 7 */
    printf("[8/8] Analyzing channels...\n");
    if (file_all_analyze_channels(fd) != 0) {
        file_all_free(fd);
        return 1;
    }
    
    /* 写入结果 */
    printf("\nWriting results...\n");
    file_all_write_results(fd, output_dir);
    
    clock_t t_end = clock();
    double elapsed = (double)(t_end - t_start) / CLOCKS_PER_SEC;
    
    /* 打印汇总 */
    printf("\n=== Summary ===\n");
    printf("Total events:     %zu\n", fd->event_size);
    printf("CH1 events (<14820): %zu, rate: %.6f\n",
           fd->event_count_ch1,
           (double)fd->event_count_ch1 / fd->event_size);
    printf("CH7 events (<14820): %zu, rate: %.6f\n",
           fd->event_count_ch7,
           (double)fd->event_count_ch7 / fd->event_size);
    printf("Elapsed time:     %.2f seconds\n", elapsed);
    
    /* 清理 */
    file_all_free(fd);
    
    printf("\nDone.\n");
    return 0;
}
