cmake_minimum_required(VERSION 3.16)
project(horse_data C)

add_library(horse_data STATIC
    genes_dat.c
    tmx_map.c
)

target_include_directories(horse_data PUBLIC include)

if(MSVC)
    target_compile_options(horse_data PRIVATE /W4)
else()
    target_compile_options(horse_data PRIVATE -Wall -Wextra)
endif()

add_executable(horse_data_cli horse_data_cli.c)
target_link_libraries(horse_data_cli PRIVATE horse_data)
