cmake_minimum_required(VERSION 3.10)
project(PDS1500_Analysis C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# 头文件路径
include_directories(${CMAKE_SOURCE_DIR}/include)

# 源文件
set(SOURCES
    src/file_all.c
    src/main.c
)

# 可执行文件
add_executable(pds1500_analysis ${SOURCES})

# 数学库
target_link_libraries(pds1500_analysis m)

# 编译选项
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(pds1500_analysis PRIVATE -Wall -Wextra -O2)
endif()
