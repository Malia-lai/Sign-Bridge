import { Landmark } from '../types';

// Helper to generate simulated 21 hand landmarks for various gestures
export function getSimulatedHand(
  gesture: string,
  time: number,
  handSide: 'Right' | 'Left' = 'Right'
): { landmarks: Landmark[]; label: 'Right' | 'Left' }[] {
  const isRight = handSide === 'Right';
  const xCenter = isRight ? 0.5 : 0.35;
  const yCenter = 0.55;
  
  // Natural micro-motion
  const wobbleX = Math.sin(time * 2) * 0.005;
  const wobbleY = Math.cos(time * 2.5) * 0.005;

  const wrist: Landmark = { x: xCenter + wobbleX, y: yCenter + wobbleY, z: 0 };

  // Base finger templates
  // Finger definition: [mcpX, mcpY, pipOffset, dipOffset, tipOffset]
  const createHandLandmarks = (fingerStates: {
    thumb: { extended: boolean; down?: boolean; pinched?: boolean };
    index: { extended: boolean; pinched?: boolean };
    middle: { extended: boolean; pinched?: boolean };
    ring: { extended: boolean; pinched?: boolean };
    pinky: { extended: boolean; pinched?: boolean };
    tiltAngle?: number; // radians
  }): Landmark[] => {
    const lms: Landmark[] = new Array(21);
    lms[0] = wrist;

    const angle = fingerStates.tiltAngle || 0;
    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);

    const rotatePoint = (px: number, py: number): [number, number] => {
      const relX = px - wrist.x;
      const relY = py - wrist.y;
      const rotX = relX * cosA - relY * sinA;
      const rotY = relX * sinA + relY * cosA;
      return [wrist.x + rotX, wrist.y + rotY];
    };

    // Thumb
    const tExt = fingerStates.thumb.extended;
    const tDown = fingerStates.thumb.down;
    const tPinch = fingerStates.thumb.pinched;

    const thumbDir = isRight ? -1 : 1;
    if (tDown) {
      // Thumb pointed down
      lms[1] = { x: wrist.x + thumbDir * 0.04, y: wrist.y + 0.03, z: -0.01 };
      lms[2] = { x: wrist.x + thumbDir * 0.07, y: wrist.y + 0.07, z: -0.02 };
      lms[3] = { x: wrist.x + thumbDir * 0.09, y: wrist.y + 0.12, z: -0.03 };
      lms[4] = { x: wrist.x + thumbDir * 0.10, y: wrist.y + 0.18, z: -0.04 };
    } else if (tPinch) {
      // Pinched towards index tip
      lms[1] = { x: wrist.x + thumbDir * 0.04, y: wrist.y - 0.04, z: -0.01 };
      lms[2] = { x: wrist.x + thumbDir * 0.07, y: wrist.y - 0.08, z: -0.02 };
      lms[3] = { x: wrist.x + thumbDir * 0.06, y: wrist.y - 0.12, z: -0.02 };
      lms[4] = { x: wrist.x + thumbDir * 0.03, y: wrist.y - 0.14, z: -0.01 };
    } else if (tExt) {
      // Thumb extended out
      lms[1] = { x: wrist.x + thumbDir * 0.04, y: wrist.y - 0.04, z: -0.01 };
      lms[2] = { x: wrist.x + thumbDir * 0.09, y: wrist.y - 0.08, z: -0.02 };
      lms[3] = { x: wrist.x + thumbDir * 0.13, y: wrist.y - 0.12, z: -0.03 };
      lms[4] = { x: wrist.x + thumbDir * 0.17, y: wrist.y - 0.15, z: -0.04 };
    } else {
      // Thumb folded across palm
      lms[1] = { x: wrist.x + thumbDir * 0.03, y: wrist.y - 0.03, z: -0.01 };
      lms[2] = { x: wrist.x + thumbDir * 0.05, y: wrist.y - 0.06, z: -0.02 };
      lms[3] = { x: wrist.x + thumbDir * 0.04, y: wrist.y - 0.08, z: -0.01 };
      lms[4] = { x: wrist.x + thumbDir * 0.02, y: wrist.y - 0.09, z: 0 };
    }

    // Helper for 4 fingers (index, middle, ring, pinky)
    const addFinger = (
      baseIdx: number,
      mcpRelX: number,
      extended: boolean,
      pinched: boolean = false,
      spreadX: number = 0
    ) => {
      const mcpY = wrist.y - 0.13;
      const mcpX = wrist.x + mcpRelX;

      let pipX: number, pipY: number, dipX: number, dipY: number, tipX: number, tipY: number;

      if (pinched) {
        pipX = mcpX + spreadX * 0.5;
        pipY = mcpY - 0.04;
        dipX = wrist.x + (isRight ? -0.01 : 0.01);
        dipY = mcpY - 0.08;
        tipX = wrist.x + (isRight ? 0.01 : -0.01);
        tipY = wrist.y - 0.14;
      } else if (extended) {
        pipX = mcpX + spreadX * 0.4;
        pipY = mcpY - 0.07;
        dipX = mcpX + spreadX * 0.7;
        dipY = mcpY - 0.13;
        tipX = mcpX + spreadX;
        tipY = mcpY - 0.19;
      } else {
        // Curled finger
        pipX = mcpX;
        pipY = mcpY - 0.04;
        dipX = mcpX;
        dipY = mcpY - 0.01;
        tipX = mcpX;
        tipY = mcpY + 0.03;
      }

      // Rotate if needed
      const [rMcpX, rMcpY] = rotatePoint(mcpX, mcpY);
      const [rPipX, rPipY] = rotatePoint(pipX, pipY);
      const [rDipX, rDipY] = rotatePoint(dipX, dipY);
      const [rTipX, rTipY] = rotatePoint(tipX, tipY);

      lms[baseIdx] = { x: rMcpX, y: rMcpY, z: -0.01 };
      lms[baseIdx + 1] = { x: rPipX, y: rPipY, z: -0.02 };
      lms[baseIdx + 2] = { x: rDipX, y: rDipY, z: -0.03 };
      lms[baseIdx + 3] = { x: rTipX, y: rTipY, z: -0.04 };
    };

    // Index (5-8)
    addFinger(5, isRight ? -0.04 : 0.04, fingerStates.index.extended, fingerStates.index.pinched, isRight ? -0.02 : 0.02);
    // Middle (9-12)
    addFinger(9, 0, fingerStates.middle.extended, fingerStates.middle.pinched, 0);
    // Ring (13-16)
    addFinger(13, isRight ? 0.04 : -0.04, fingerStates.ring.extended, fingerStates.ring.pinched, isRight ? 0.01 : -0.01);
    // Pinky (17-20)
    addFinger(17, isRight ? 0.08 : -0.08, fingerStates.pinky.extended, fingerStates.pinky.pinched, isRight ? 0.03 : -0.03);

    return lms;
  };

  const g = gesture.toLowerCase();

  if (g === 'hello') {
    // Open palm waving slightly
    const wave = Math.sin(time * 3) * 0.1;
    const lms = createHandLandmarks({
      thumb: { extended: true },
      index: { extended: true },
      middle: { extended: true },
      ring: { extended: true },
      pinky: { extended: true },
      tiltAngle: wave,
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'peace') {
    // V sign
    const lms = createHandLandmarks({
      thumb: { extended: false },
      index: { extended: true },
      middle: { extended: true },
      ring: { extended: false },
      pinky: { extended: false },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'love') {
    // ILY: thumb, index, pinky
    const lms = createHandLandmarks({
      thumb: { extended: true },
      index: { extended: true },
      middle: { extended: false },
      ring: { extended: false },
      pinky: { extended: true },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'i') {
    // ASL 'I': pinky only
    const lms = createHandLandmarks({
      thumb: { extended: false },
      index: { extended: false },
      middle: { extended: false },
      ring: { extended: false },
      pinky: { extended: true },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'eat') {
    // Bunched fingers
    const lms = createHandLandmarks({
      thumb: { extended: false, pinched: true },
      index: { extended: false, pinched: true },
      middle: { extended: false, pinched: true },
      ring: { extended: false, pinched: true },
      pinky: { extended: false, pinched: true },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'sleep') {
    // Tilted flat hand
    const lms = createHandLandmarks({
      thumb: { extended: false },
      index: { extended: true },
      middle: { extended: true },
      ring: { extended: true },
      pinky: { extended: true },
      tiltAngle: 0.9, // 50 degrees
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'not') {
    // Thumb up
    const lms = createHandLandmarks({
      thumb: { extended: true },
      index: { extended: false },
      middle: { extended: false },
      ring: { extended: false },
      pinky: { extended: false },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'hate') {
    // Thumb down
    const lms = createHandLandmarks({
      thumb: { extended: true, down: true },
      index: { extended: false },
      middle: { extended: false },
      ring: { extended: false },
      pinky: { extended: false },
    });
    return [{ landmarks: lms, label: 'Right' }];
  }

  if (g === 'shawarma' || g === 'tacos') {
    // Two hands
    const hand1 = createHandLandmarks({
      thumb: { extended: true },
      index: { extended: true },
      middle: { extended: true },
      ring: { extended: true },
      pinky: { extended: true },
      tiltAngle: -0.4,
    });
    const hand2 = createHandLandmarks({
      thumb: { extended: true },
      index: { extended: true },
      middle: { extended: true },
      ring: { extended: true },
      pinky: { extended: true },
      tiltAngle: 0.4,
    });
    // Shift hand 2 to left
    hand2.forEach((p) => {
      p.x -= 0.18;
    });

    return [
      { landmarks: hand1, label: 'Right' },
      { landmarks: hand2, label: 'Left' },
    ];
  }

  // Default to open palm
  const lms = createHandLandmarks({
    thumb: { extended: true },
    index: { extended: true },
    middle: { extended: true },
    ring: { extended: true },
    pinky: { extended: true },
  });
  return [{ landmarks: lms, label: 'Right' }];
}
