# Project Cycle And Feasibility

## Summary

The project is feasible within one quarter if execution stays focused on:

- a single runtime baseline: `CARLA 0.9.15 / UE4.26`
- one stable stack: `stable`
- one primary host: the company Ubuntu machine

## What Is Feasible Now

- control-plane automation
- digest and project tracking
- stable stack render/plan generation
- public-road asset normalization
- BEV / VAD / UniAD-style / E2E shadow research on the same stable stack

## What Is Not The Gate

- any separate simulator runtime
- a second simulator stack
- replacing the stable planning/control chain with direct E2E control

## Quarter Acceptance

- at least one repeatable stable closed-loop result
- at least one repeatable report and replay output
- at least one reusable public-road asset bundle
- at least one E2E shadow comparison scenario on CARLA 0.9.15
