# Google vs Facebook DCN
---
## Google DCN (Jupiter)
- Use middle path regarding building block size.
- Centauri chassis for unit deployment, contains 4 switches.
- All ports were accessible on the front panel of the chassis.
- Using Centauri switch as a ToR switch.
- The logical topology of an middle block was a 2-stage blocking network.
- Each ToR chip connection has dual redundant links, which aids fast reconvergence for the common case of single link failure or maintenance.
- Supports 1.3 Pbps bisection bandwidth
- They build their own control plane for the need to route across a largely static topology with massive multipath.
- Before Jupiter, google make use of the standard BGP for route exchange at the edge of fabric, redistributing BGP-learned routes through Firepath.


## Facebook DCN
- Broke network into small server pods
- Create uniform high-performance connectivity between pods.
- Each pod is served by four fabric switches.
- Due to its small size, it easily fits into data center floor plans and requires mid-size switches to aggregate the ToRs.
- Each Downlink port to a ToR has an equal amount of uplink capacity on the switches.
- Four "planes" of spine switches, with up to 48 devices within, and each fabric switch of each pod connects to each spine switch within its local plane.
- With the pods and planes, it forms a modular network topology with many 10G-connected servers, scaling to multi-petabit bandwidth and covering data center building with non-oversubscribed rack-to rack performance.
- Equipped fabric with number of edge pods for external connectivity.
- Fabric makes use of ECMP, with flow-based hashing.
- To prevent "elephant flows", made all network multi-speed.
- Developed a centralized BGP controller to override routing paths on the fabric by only software decisions.