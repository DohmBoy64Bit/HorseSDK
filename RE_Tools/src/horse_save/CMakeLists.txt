cmake_minimum_required(VERSION 3.16)
project(horse_save C)

add_library(horse_save STATIC
    horse_save_stream.c
    horse_save_gene.c
    horse_save_nested.c
    horse_save_parse.c
    horse_save_b8.c
    horse_save_api.c
)

target_include_directories(horse_save PUBLIC include)

add_executable(horse_save_cli horse_save_cli.c)
target_link_libraries(horse_save_cli PRIVATE horse_save)

if(MSVC)
    target_compile_options(horse_save PRIVATE /W4)
else()
    target_compile_options(horse_save PRIVATE -Wall -Wextra)
endif()
