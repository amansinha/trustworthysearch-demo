#!/bin/zsh

convert Grid_U.png Grid_G.png +append -background white -gravity center -splice 300x0+0+0 Grid.png
convert MC_U.png MC_G.png +append -background white -gravity center -splice 300x0+0+0 MC.png
convert Stress_U.png Stress_G.png +append -background white -gravity center -splice 300x0+0+0 Stress.png
convert Risk_U.png Risk_G.png +append -background white -gravity center -splice 300x0+0+0 Risk.png
