﻿import Rhino as rc
import scriptcontext as sc
import Grasshopper.Kernel as gh
from System import Object
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import rhinoscriptsyntax as rs

tolerance = sc.doc.ModelAbsoluteTolerance

def checkTheInputs():
    if len(_bldgMasses) != 0 and _bldgMasses[0]!=None :
        #Check for guid
        for i,b in enumerate(_bldgMasses):
            if type(b)==type(rs.AddPoint(0,0,0)):
                _bldgMasses[i] = rs.coercebrep(b)
        
        brepSolid = []
        for brep in _bldgMasses:
            if brep.IsSolid == True:
                brepSolid.append(1)
            else:
                warning = "Building masses must be closed solids!"
                print warning
                w = gh.GH_RuntimeMessageLevel.Warning
                ghenv.Component.AddRuntimeMessage(w, warning)
        if sum(brepSolid) == len(_bldgMasses):
            checkData1 = True
        
    else:
        checkData1 = False
        print "Connect closed solid building masses to split them up into zones."
    
    if perimeterZoneDepth_ == []:
        print "No value is connected for zone depth and so the model will not be divided up into perimeter and core zones."
    else: pass
    
    if perimeterZoneDepth_ != []:
        checkData2 = True
    else:
        checkData2 = False
        print "A value must be conneted for perimeterZoneDepth_ in order to run."
    
    if checkData1 == True and checkData2 == True:
        checkData = True
    else: checkData = False
    
    return checkData
#Define a function that will extract the points from a polycurve line
def getCurvePoints(curve):
    exploCurve = rc.Geometry.PolyCurve.DuplicateSegments(curve)
    individPts = []
    for line in exploCurve:
        individPts.append(line.PointAtStart)
    return individPts
#Define a function that cleans up curves by deleting out points that lie in a line and leaves the curved segments intact.  Also, have it delete out any segments that are shorter than the tolerance.
def cleanCurve(curve, curvePts, offsetDepth):
    #First check if there are any curved segements and make a list to keep track of this
    curveBool = []
    exploCurve = rc.Geometry.PolyCurve.DuplicateSegments(curve)
    for segment in exploCurve:
        if segment.IsLinear() == False: curveBool.append(True)
        else: curveBool.append(False)
    
    #Test if any of the points lie in a line and use this to generate a new list of curve segments and points.
    newPts = []
    newSegments = []
    for pointCount, point in enumerate(curvePts):
        testLine = rc.Geometry.Line(point, curvePts[pointCount-2])
        if testLine.DistanceTo(curvePts[pointCount-1], True) > tolerance and len(newPts) == 0:
            newPts.append(curvePts[pointCount-1])
        elif testLine.DistanceTo(curvePts[pointCount-1], True) > tolerance and curveBool[pointCount-2] == False and len(newPts) != 0:
            newSegments.append(rc.Geometry.LineCurve(newPts[-1], curvePts[pointCount-1]))
            newPts.append(curvePts[pointCount-1])
        elif curveBool[pointCount-2] == True and exploCurve[pointCount-2].GetLength()>offsetDepth/25:
            newPts.append(curvePts[pointCount-1])
            newSegments.append(exploCurve[pointCount-2])
        elif curveBool[pointCount-2] == True and curveBool[pointCount-1] == True and exploCurve[pointCount-2].GetLength()<offsetDepth/25:
            for counting, curve in enumerate(exploCurve):
                if counting == pointCount-1:
                    transformMatrix = rc.Geometry.Transform.Translation(exploCurve[pointCount-1].PointAtStart.X - exploCurve[pointCount-2].PointAtEnd.X, exploCurve[pointCount-1].PointAtStart.Y - exploCurve[pointCount-2].PointAtEnd.Y, exploCurve[pointCount-1].PointAtStart.Z - exploCurve[pointCount-2].PointAtEnd.Z)
                    curve.PointAtStart.Transform(transformMatrix)
                else: pass
        else: pass
    
    #Add a segment to close the curves and join them together into one polycurve.
    if curveBool[-2] == True and exploCurve[-2].GetLength()>offsetDepth/25:
        newSegments.append(exploCurve[-2])
    elif curveBool[-2] == False:
        newSegments.append(rc.Geometry.LineCurve(newPts[-1], newPts[0]))
    else:
        pass
    
    #Shift the lists over by 1 to ensure that the order of the points and curves match the input
    newCurvePts = newPts[1:]
    newCurvePts.append(newPts[0])
    newCurveSegments = newSegments[1:]
    newCurveSegments.append(newSegments[0])
    
    #Join the segments together into one curve.
    newCrv = rc.Geometry.PolyCurve()
    for seg in newCurveSegments:
        newCrv.Append(seg)
    newCrv.MakeClosed(tolerance)
    
    #return the new curve and the list of points associated with it.
    return newCrv, newCurvePts, newCurveSegments
def splitPerimZones(mass, zoneDepth, floorCrvList, topInc, totalNurbsList):
    finalZones = []
    coreZoneWallList = []
    genFailure = False

    #define a value to keep track of whether this is a courtyard building.
    if len(floorCrvList) > 1: doNotGenCore = True
    else: doNotGenCore = False
    
    for listCount, floorCrvs in enumerate(floorCrvList):
        nurbsList = totalNurbsList[listCount]
        #Get a list of curves that represent the ceiling (without the top floor). Generate a list of points for each and a brep for the ceiling surface.
        ceilingCrv = floorCrvs[1:]
        ceilingPts = []
        for curveCount, curve in enumerate(ceilingCrv):
            ceilingPts.append(getCurvePoints(curve))
        
        #Get a list of curves that represent the floors (without the top floor). Generate a list of points for each and a brep for the ceiling surface.
        floorCrv = floorCrvs[:-1]
        floorPts = []
        for curveCount, curve in enumerate(floorCrv):
            floorPts.append(getCurvePoints(curve))
        
        #Find the offset depth for each of the floors.
        numOfFlr = len(floorCrv)
        flrDepths = []
        for depth in zoneDepth:
            if '@' in depth:
                zoneD = float(depth.split('@')[1])
                try: numFlr = int(depth.split('@')[0])
                except: numFlr = numOfFlr
                for floors in range(numFlr): flrDepths.append(zoneD)
            else:
                zoneD = float(depth)
                flrDepths.append(zoneD)
        
        #Clean up the input curves, This involves testing to see if any 3 points on the floor or ceiling curves lie in a line and, if so, deleting out the redundant mid point.
        newFloorCrv = []
        newFloorPts = []
        for count, curve in enumerate(floorCrv):
            newFCrv, newFCrvPts, newFCrvSeg = cleanCurve(curve, floorPts[count], flrDepths[0])
            newFloorCrv.append(newFCrv)
            newFloorPts.append(newFCrvPts)
        floorCrv = newFloorCrv
        floorPts = newFloorPts
        
        newCeilingCrv = []
        newCeilingPts = []
        for count, curve in enumerate(ceilingCrv):
            newCCrv, newCCrvPts, newCCrvSeg  = cleanCurve(curve, ceilingPts[count], flrDepths[0])
            newCeilingCrv.append(newCCrv)
            newCeilingPts.append(newCCrvPts)
        ceilingCrv = newCeilingCrv
        ceilingPts = newCeilingPts
        
        
        #Offset the curve for each floor and use the results to create new core and perimeter zones
        
        for curveCount, curve in enumerate(floorCrv):
            try:
                #If the curves are originally Nurbs curves, Offset them with "None", corners.  Otherwise, offset them with sharp corners.
                #Offset the curves and check to be sure that they are being offset in the right direction.
                if nurbsList[curveCount] == True and listCount == 0:
                    offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    offsetFloorCrv.MakeClosed(tolerance)
                    if str(offsetFloorCrv.Contains(floorPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Inside":
                        offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    else: pass
                elif listCount == 0:
                    offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    offsetFloorCrv.MakeClosed(tolerance)
                    if str(offsetFloorCrv.Contains(floorPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Inside":
                        offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    else: pass
                elif nurbsList[curveCount] == True and listCount != 0:
                    offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    offsetFloorCrv.MakeClosed(tolerance)
                    if str(offsetFloorCrv.Contains(floorPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Outside":
                        offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    else: pass
                else:
                    offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    offsetFloorCrv.MakeClosed(tolerance)
                    if str(offsetFloorCrv.Contains(floorPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Outside":
                        offsetFloorCrv = curve.Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    else: pass
                
                offsetFloorPts = getCurvePoints(offsetFloorCrv)
                
                if nurbsList[curveCount] == True and listCount == 0:
                    offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    offsetCeilingCrv.MakeClosed(tolerance)
                    if str(offsetCeilingCrv.Contains(ceilingPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Inside":
                        offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    else: pass
                elif listCount == 0:
                    offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    offsetCeilingCrv.MakeClosed(tolerance)
                    if str(offsetCeilingCrv.Contains(ceilingPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Inside":
                        offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    else: pass
                elif nurbsList[curveCount] == True and listCount != 0:
                    offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    offsetCeilingCrv.MakeClosed(tolerance)
                    if str(offsetCeilingCrv.Contains(ceilingPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Outside":
                        offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.None)[0]
                    else: pass
                else:
                    offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, -flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    offsetCeilingCrv.MakeClosed(tolerance)
                    if str(offsetCeilingCrv.Contains(ceilingPts[curveCount][0], rc.Geometry.Plane.WorldXY, tolerance)) == "Outside":
                        offsetCeilingCrv = ceilingCrv[curveCount].Offset(rc.Geometry.Plane.WorldXY, flrDepths[curveCount], tolerance, rc.Geometry.CurveOffsetCornerStyle.Sharp)[0]
                    else: pass
                
                offsetCeilingPts = getCurvePoints(offsetCeilingCrv)
                
                #Clean up the offset curves, This involves testing to see if any 3 points on the floor or ceiling curves lie in a line and, if so, deleting out the redundant mid point.
                offsetFloorCrv, offsetFloorPts, offsetFloorCrvSegments = cleanCurve(offsetFloorCrv, offsetFloorPts, flrDepths[0])
                offsetCeilingCrv, offsetCeilingPts, offsetCeilingCrvSegments = cleanCurve(offsetCeilingCrv, offsetCeilingPts, flrDepths[0])
                
                #Test to see if the number of segments of the offset curve is the same as that of the original curve.  If not, this component cannot handle such a calculation.
                checkCurveSeg = False
                if len(rc.Geometry.PolyCurve.DuplicateSegments(offsetFloorCrv)) == len(rc.Geometry.PolyCurve.DuplicateSegments(floorCrv[curveCount])) and len(rc.Geometry.PolyCurve.DuplicateSegments(offsetCeilingCrv)) == len(rc.Geometry.PolyCurve.DuplicateSegments(ceilingCrv[curveCount])):
                    checkCurveSeg = True
                else: pass
                
                #If the geometry fails the segment count test above but was originally a single nurbs curve, it is still possible to generate zones for it.
                #We just have to split up the outside curve into the same number of segments using the closest points.
                if checkCurveSeg == False and nurbsList[curveCount] == True:
                    closestOuterPointParams = []
                    for point in offsetFloorPts:
                        closestOuterPointParams.append(floorCrv[curveCount].ClosestPoint(point)[1])
                    closestOuterPointParamsFinal = closestOuterPointParams[1:]
                    outerFloorPts = []
                    for param in closestOuterPointParamsFinal:
                        outerFloorPts.append(floorCrv[curveCount].PointAt(param))
                    splitCurve = floorCrv[curveCount].Split(closestOuterPointParamsFinal)
                    finalJoinedCurve = rc.Geometry.PolyCurve()
                    for curveSeg in splitCurve:
                        finalJoinedCurve.Append(curveSeg)
                    finalJoinedCurve.MakeClosed(tolerance)
                    if finalJoinedCurve.SegmentCount == offsetFloorCrv.SegmentCount:
                        floorCrv[curveCount] = finalJoinedCurve
                        floorPts[curveCount] = getCurvePoints(finalJoinedCurve)
                        checkCurveSeg1 = True
                    else: checkCurveSeg1 = False
                    
                    closestOuterPointParams = []
                    for point in offsetCeilingPts:
                        closestOuterPointParams.append(ceilingCrv[curveCount].ClosestPoint(point)[1])
                    closestOuterPointParamsFinal = closestOuterPointParams[1:]
                    splitCurve = ceilingCrv[curveCount].Split(closestOuterPointParamsFinal)
                    finalJoinedCurve = rc.Geometry.PolyCurve()
                    for curveSeg in splitCurve:
                        finalJoinedCurve.Append(curveSeg)
                    finalJoinedCurve.MakeClosed(tolerance)
                    if finalJoinedCurve.SegmentCount == offsetCeilingCrv.SegmentCount:
                        ceilingCrv[curveCount] = finalJoinedCurve
                        ceilingPts[curveCount] = getCurvePoints(finalJoinedCurve)
                        checkCurveSeg2 = True
                    else: checkCurveSeg2 = False
                    
                    if checkCurveSeg1 == True and checkCurveSeg2 == True:
                        checkCurveSeg = True
                    else: pass
                
                
                if checkCurveSeg == True:
                    #Test to see which points on the inside of the floor and ceiling curves are closest to those on the outside.
                    floorConnectionPts = []
                    for point in offsetFloorPts:
                        pointDist = []
                        floorEdgePts = floorPts[curveCount][:]
                        for perimPoint in floorEdgePts:
                            pointDist.append(rc.Geometry.Point3d.DistanceTo(point, perimPoint))
                        sortDist = [x for (y,x) in sorted(zip(pointDist, floorEdgePts))]
                        pointDist.sort()
                        floorConnectionPts.append(sortDist[0])
                    
                    ceilingConnectionPts = []
                    for point in offsetCeilingPts:
                        pointDist = []
                        ceilingEdgePts = ceilingPts[curveCount][:]
                        for perimPoint in ceilingEdgePts:
                            pointDist.append(rc.Geometry.Point3d.DistanceTo(point, perimPoint))
                        sortDist = [x for (y,x) in sorted(zip(pointDist, ceilingEdgePts))]
                        ceilingConnectionPts.append(sortDist[0])
                    
                    #Create lines from the points of the offset curve to the closest point on the outside curve in order to split up the the offset boundary into different perimeter zones.
                    zoneFloorCurves = []
                    for pointCount, point in enumerate(offsetFloorPts):
                        floorZoneCurve = rc.Geometry.LineCurve(point, floorConnectionPts[pointCount])
                        zoneFloorCurves.append(floorZoneCurve)
                    
                    zoneCeilingCurves = []
                    for pointCount, point in enumerate(offsetCeilingPts):
                        ceilingCurves = rc.Geometry.LineCurve(point, ceilingConnectionPts[pointCount])
                        zoneCeilingCurves.append(ceilingCurves)
                    
                    #Determine which of the lines on the ceiling are closest to those on the floor and vice-versa.  This will determine which lines should be lofted to create interior partitions.
                    ceilingConnectionLines = []
                    for line in zoneFloorCurves:
                        lineDist = []
                        ceilingConnectors = zoneCeilingCurves[:]
                        for connectLine in ceilingConnectors:
                            lineDist.append(rc.Geometry.Point3d.DistanceTo(line.PointAt(0.5), connectLine.PointAt(0.5)))
                        sortDist = [x for (y,x) in sorted(zip(lineDist, ceilingConnectors))]
                        ceilingConnectionLines.append(sortDist[0])
                    
                    floorConnectionLines = []
                    for line in zoneCeilingCurves:
                        lineDist = []
                        floorConnectors = zoneFloorCurves[:]
                        for connectLine in floorConnectors:
                            lineDist.append(rc.Geometry.Point3d.DistanceTo(line.PointAt(0.5), connectLine.PointAt(0.5)))
                        sortDist = [x for (y,x) in sorted(zip(lineDist, floorConnectors))]
                        floorConnectionLines.append(sortDist[0])
                    
                    #Loft the floor and ceiling curves together in order to get walls that divide up the perimeter zones.
                    floorWalls = []
                    ceilingWalls = []
                    for lineCount, line in enumerate(zoneFloorCurves):
                        floorWalls.append(rc.Geometry.Brep.CreateFromLoft([line, ceilingConnectionLines[lineCount]], rc.Geometry.Point3d.Unset, rc.Geometry.Point3d.Unset, rc.Geometry.LoftType.Normal, False)[0])
                    for lineCount, line in enumerate(zoneCeilingCurves):
                        ceilingWalls.append(rc.Geometry.Brep.CreateFromLoft([floorConnectionLines[lineCount], line], rc.Geometry.Point3d.Unset, rc.Geometry.Point3d.Unset, rc.Geometry.LoftType.Normal, False)[0])
                    
                    #Make a function that pulls out the interior and exterior points of each perimeter wall brep.
                    def getIntAndExtVert(brep):
                        vert = brep.DuplicateVertices()
                        intVert = []
                        extVert = []
                        for point in vert:
                            for otherPoint in offsetFloorPts:
                                if point.X < otherPoint.X + tolerance and  point.X > otherPoint.X - tolerance and point.Y < otherPoint.Y + tolerance and  point.Y > otherPoint.Y - tolerance and point.Z < otherPoint.Z + tolerance and  point.Z > otherPoint.Z - tolerance:
                                    intVert.append(point)
                                else: pass
                            for otherPoint in offsetCeilingPts:
                                if point.X < otherPoint.X + tolerance and  point.X > otherPoint.X - tolerance and point.Y < otherPoint.Y + tolerance and  point.Y > otherPoint.Y - tolerance and point.Z < otherPoint.Z + tolerance and  point.Z > otherPoint.Z - tolerance:
                                    intVert.append(point)
                                else: pass
                        for point in vert:
                            for otherPoint in floorPts[curveCount]:
                                if point.X < otherPoint.X + tolerance and  point.X > otherPoint.X - tolerance and point.Y < otherPoint.Y + tolerance and  point.Y > otherPoint.Y - tolerance and point.Z < otherPoint.Z + tolerance and  point.Z > otherPoint.Z - tolerance:
                                    extVert.append(point)
                                else: pass
                            for otherPoint in ceilingPts[curveCount]:
                                if point.X < otherPoint.X + tolerance and  point.X > otherPoint.X - tolerance and point.Y < otherPoint.Y + tolerance and  point.Y > otherPoint.Y - tolerance and point.Z < otherPoint.Z + tolerance and  point.Z > otherPoint.Z - tolerance:
                                    extVert.append(point)
                                else: pass
                        return intVert, extVert
                    
                    #Test whetther all of the curves in the floor and ceiling are curved.
                    nurbTestList = []
                    for nurb in nurbsList:
                        if nurb == True: nurbTestList.append(1)
                        else: pass
                    if sum(nurbTestList) == len(nurbsList): totalNurbTest = True
                    else: totalNurbTest = False
                    
                    #Get a list of the exterior curves, which will be used to remove bad walls in the next step.
                    testEdgeCurves = []
                    edgeCurves = mass[curveCount].DuplicateEdgeCurves(False)
                    zHeight = []
                    for edgeCrv in edgeCurves:
                        zHeight.append((edgeCrv.PointAtStart.Z +edgeCrv.PointAtEnd.Z)/2)
                    edgeCurves = [x for (y,x) in sorted(zip(zHeight, edgeCurves))]
                    zHeight.sort()
                    zMin = zHeight[0]
                    zMax = zHeight[-1]
                    for heightCount, height in enumerate(zHeight):
                        if height > zMin + tolerance and height < zMax - tolerance:
                            testEdgeCurves.append(edgeCurves[heightCount])
                        else: pass
                    #for wall in floorWalls:
                    #    print rc.Geometry.AreaMassProperties.Compute(wall).Area
                    #Make the list of perimeter zone walls.
                    perimZoneWalls = []
                    
                    #If the geometry is all planar, check the perimeter walls against the exterior curves.
                    if totalNurbTest == False:
                        for wallCount, wall in enumerate(floorWalls):
                            wallIntVert, wallExtVert = getIntAndExtVert(wall)
                            foundIt = False
                            for testLine in testEdgeCurves:
                                if testLine.PointAtStart.X > wallExtVert[0].X - tolerance and testLine.PointAtStart.X < wallExtVert[0].X + tolerance and testLine.PointAtEnd.X > wallExtVert[1].X - tolerance and testLine.PointAtEnd.X < wallExtVert[1].X + tolerance and testLine.PointAtStart.Y > wallExtVert[0].Y - tolerance and testLine.PointAtStart.Y < wallExtVert[0].Y + tolerance and testLine.PointAtEnd.Y > wallExtVert[1].Y - tolerance and testLine.PointAtEnd.Y < wallExtVert[1].Y + tolerance and testLine.PointAtStart.Z > wallExtVert[0].Z - tolerance and testLine.PointAtStart.Z < wallExtVert[0].Z + tolerance and testLine.PointAtEnd.Z > wallExtVert[1].Z - tolerance and testLine.PointAtEnd.Z < wallExtVert[1].Z + tolerance:
                                    foundIt = True
                                elif testLine.PointAtStart.X > wallExtVert[1].X - tolerance and testLine.PointAtStart.X < wallExtVert[1].X + tolerance and testLine.PointAtEnd.X > wallExtVert[0].X - tolerance and testLine.PointAtEnd.X < wallExtVert[0].X + tolerance and testLine.PointAtStart.Y > wallExtVert[1].Y - tolerance and testLine.PointAtStart.Y < wallExtVert[1].Y + tolerance and testLine.PointAtEnd.Y > wallExtVert[0].Y - tolerance and testLine.PointAtEnd.Y < wallExtVert[0].Y + tolerance and testLine.PointAtStart.Z > wallExtVert[1].Z - tolerance and testLine.PointAtStart.Z < wallExtVert[1].Z + tolerance and testLine.PointAtEnd.Z > wallExtVert[0].Z - tolerance and testLine.PointAtEnd.Z < wallExtVert[0].Z + tolerance:
                                    foundIt = True
                                else:pass
                            if foundIt == True:
                                perimZoneWalls.append(wall)
                        
                        insertIndex = 0
                        lastTri = False
                        for wallCount, wall in enumerate(ceilingWalls):
                            wallIntVert, wallExtVert = getIntAndExtVert(wall)
                            foundIt = False
                            for testLine in testEdgeCurves:
                                if testLine.PointAtStart.X > wallExtVert[0].X - tolerance and testLine.PointAtStart.X < wallExtVert[0].X + tolerance and testLine.PointAtEnd.X > wallExtVert[1].X - tolerance and testLine.PointAtEnd.X < wallExtVert[1].X + tolerance and testLine.PointAtStart.Y > wallExtVert[0].Y - tolerance and testLine.PointAtStart.Y < wallExtVert[0].Y + tolerance and testLine.PointAtEnd.Y > wallExtVert[1].Y - tolerance and testLine.PointAtEnd.Y < wallExtVert[1].Y + tolerance and testLine.PointAtStart.Z > wallExtVert[0].Z - tolerance and testLine.PointAtStart.Z < wallExtVert[0].Z + tolerance and testLine.PointAtEnd.Z > wallExtVert[1].Z - tolerance and testLine.PointAtEnd.Z < wallExtVert[1].Z + tolerance:
                                    foundIt = True
                                elif testLine.PointAtStart.X > wallExtVert[1].X - tolerance and testLine.PointAtStart.X < wallExtVert[1].X + tolerance and testLine.PointAtEnd.X > wallExtVert[0].X - tolerance and testLine.PointAtEnd.X < wallExtVert[0].X + tolerance and testLine.PointAtStart.Y > wallExtVert[1].Y - tolerance and testLine.PointAtStart.Y < wallExtVert[1].Y + tolerance and testLine.PointAtEnd.Y > wallExtVert[0].Y - tolerance and testLine.PointAtEnd.Y < wallExtVert[0].Y + tolerance and testLine.PointAtStart.Z > wallExtVert[1].Z - tolerance and testLine.PointAtStart.Z < wallExtVert[1].Z + tolerance and testLine.PointAtEnd.Z > wallExtVert[0].Z - tolerance and testLine.PointAtEnd.Z < wallExtVert[0].Z + tolerance:
                                    foundIt = True
                                else:pass
                            #Check to see if the wall is a duplicate on the floor walls.
                            if foundIt == True:
                                isDulpicate = False
                                for otherCount, otherWall in enumerate(perimZoneWalls):
                                    if wall.IsDuplicate(otherWall, tolerance) == True:
                                        isDulpicate = True
                                        insertIndex = otherCount + 1
                                        lastTri = False
                                    else:pass
                            else:
                                isDulpicate = True
                                lastTri = False
                            if foundIt == True and isDulpicate == False:
                                if lastTri == True:
                                    insertIndex = insertIndex + 1
                                else: pass
                                perimZoneWalls.insert(insertIndex, wall)
                                lastTri = True
                    else:
                        #If the geometry is all curved, just generate the list starting with the floor curves and checking for duplicates.
                        perimZoneWalls = floorWalls[:]
                        insertIndex = 0
                        for wallCount, wall in enumerate(ceilingWalls):
                            isDulpicate = False
                            for otherCount, otherWall in enumerate(perimZoneWalls):
                                if wall.IsDuplicate(otherWall, tolerance) == True:
                                    isDulpicate = True
                                    insertIndex = otherCount + 1
                                else:pass
                            if isDulpicate == False:
                                perimZoneWalls.insert(insertIndex, wall)
                            else: pass
                    
                    
                    #Test to see if the core zone wall should be made by lofting a floor + ceiling curve or should be a triangle.
                    #Pair up the perimeter zone walls and check the condition between them to see if a triangle or a lofted surface should be generated for either the interior or exterior condition.
                    coreZoneWalls = []
                    exteriorZoneWalls = []
                    
                    perimWallsPairList = []
                    for wallCount, wall in enumerate(perimZoneWalls):
                        perimWallsPairList.append([perimZoneWalls[wallCount-1], wall])
                    
                    for pair in perimWallsPairList:
                        interiorTriangle = False
                        exteriorTriangle = False
                        intTriPts = []
                        extTriPts = []
                        intVertOne, extVertOne = getIntAndExtVert(pair[0])
                        intVertTwo, extVertTwo = getIntAndExtVert(pair[1])
                        
                        for pointCount, point in enumerate(intVertOne):
                            for otherPointCount, otherPoint in enumerate(intVertTwo):
                                if point.X < otherPoint.X + (0.5*tolerance) and  point.X > otherPoint.X - (0.5*tolerance) and point.Y < otherPoint.Y + (0.5*tolerance) and  point.Y > otherPoint.Y - (0.5*tolerance) and point.Z < otherPoint.Z + (0.5*tolerance) and  point.Z > otherPoint.Z - (0.5*tolerance):
                                    interiorTriangle = True
                                    intTriPts = [point, intVertOne[pointCount-1], intVertTwo[otherPointCount-1]]
                                else: pass
                        for pointCount, point in enumerate(extVertOne):
                            for otherPointCount, otherPoint in enumerate(extVertTwo):
                                if point.X < otherPoint.X + (0.5*tolerance) and  point.X > otherPoint.X - (0.5*tolerance) and point.Y < otherPoint.Y + (0.5*tolerance) and  point.Y > otherPoint.Y - (0.5*tolerance) and point.Z < otherPoint.Z + (0.5*tolerance) and  point.Z > otherPoint.Z - (0.5*tolerance):
                                    exteriorTriangle = True
                                    extTriPts = [point, extVertOne[pointCount-1], extVertTwo[otherPointCount-1]] 
                                else: pass
                        
                        #Make the core zone wall and append it to the list.
                        if interiorTriangle == True:
                            coreZoneWall = rc.Geometry.Brep.CreateFromCornerPoints(intTriPts[0], intTriPts[1], intTriPts[2], tolerance)
                        else:
                            #Find the line on the floor that is closest to both floor vertices.
                            distanceToLine = []
                            offsetFloorSegments = rc.Geometry.PolyCurve.DuplicateSegments(offsetFloorCrv)
                            for line in offsetFloorSegments:
                                lineDist = rc.Geometry.Point3d.DistanceTo(line.PointAtStart, intVertOne[0]) + rc.Geometry.Point3d.DistanceTo(line.PointAtEnd, intVertTwo[0])
                                distanceToLine.append(lineDist)
                            sortLineDist = [x for (y,x) in sorted(zip(distanceToLine, offsetFloorSegments))]
                            floorLine = sortLineDist[0]
                            #Find the line on the ceiling that is closest to both ceiling vertices.
                            distanceToLine = []
                            offsetCeilingSegments = rc.Geometry.PolyCurve.DuplicateSegments(offsetCeilingCrv)
                            for line in offsetCeilingSegments:
                                lineDist = rc.Geometry.Point3d.DistanceTo(line.PointAtStart, intVertOne[1]) + rc.Geometry.Point3d.DistanceTo(line.PointAtEnd, intVertTwo[1])
                                distanceToLine.append(lineDist)
                            sortLineDist = [x for (y,x) in sorted(zip(distanceToLine, offsetCeilingSegments))]
                            ceilingLine = sortLineDist[0]
                            #Loft the floor and ceiling together.
                            coreZoneWall = rc.Geometry.Brep.CreateFromLoft([floorLine, ceilingLine], rc.Geometry.Point3d.Unset, rc.Geometry.Point3d.Unset, rc.Geometry.LoftType.Normal, False)[0]
                        coreZoneWalls.append(coreZoneWall)
                        
                        # Make the exterior wall and append it to the list.
                        if exteriorTriangle == True:
                            exteriorZoneWall = rc.Geometry.Brep.CreateFromCornerPoints(extTriPts[0], extTriPts[1], extTriPts[2], tolerance)
                        else:
                            #Find the line on the floor that is closest to both floor vertices.
                            distanceToLine = []
                            floorSegments = rc.Geometry.PolyCurve.DuplicateSegments(floorCrv[curveCount])
                            for line in floorSegments:
                                lineDist = rc.Geometry.Point3d.DistanceTo(line.PointAtStart, extVertOne[0]) + rc.Geometry.Point3d.DistanceTo(line.PointAtEnd, extVertTwo[0])
                                distanceToLine.append(lineDist)
                            sortLineDist = [x for (y,x) in sorted(zip(distanceToLine, floorSegments))]
                            floorLine = sortLineDist[0]
                            #Find the line on the ceiling that is closest to both ceiling vertices.
                            distanceToLine = []
                            ceilingSegments = rc.Geometry.PolyCurve.DuplicateSegments(ceilingCrv[curveCount])
                            for line in ceilingSegments:
                                lineDist = rc.Geometry.Point3d.DistanceTo(line.PointAtStart, extVertOne[1]) + rc.Geometry.Point3d.DistanceTo(line.PointAtEnd, extVertTwo[1])
                                distanceToLine.append(lineDist)
                            sortLineDist = [x for (y,x) in sorted(zip(distanceToLine, ceilingSegments))]
                            ceilingLine = sortLineDist[0]
                            #Loft the floor and ceiling together.
                            exteriorZoneWall = rc.Geometry.Brep.CreateFromLoft([floorLine, ceilingLine], rc.Geometry.Point3d.Unset, rc.Geometry.Point3d.Unset, rc.Geometry.LoftType.Normal, False)[0]
                        exteriorZoneWalls.append(exteriorZoneWall)
                    
                    #Group the walls together by floor.
                    floorZones = []
                    #floorZones = perimZoneWalls
                    #floorZones.extend(exteriorZoneWalls)
                    
                    #Join the walls together to make zones.
                    joinedWalls = rc.Geometry.Brep.JoinBreps(coreZoneWalls, tolerance)[0]
                    if doNotGenCore == False:
                        coreZone = joinedWalls.CapPlanarHoles(tolerance)
                        floorZones.append(coreZone)
                    elif listCount == 0:
                        coreZoneWallList.append([joinedWalls])
                    else:
                        coreZoneWallList[curveCount].append(joinedWalls)
                    
                    perimZones = []
                    for wallCount, wall in enumerate(perimZoneWalls):
                        brepList = [wall, perimZoneWalls[wallCount-1], exteriorZoneWalls[wallCount], coreZoneWalls[wallCount]]
                        joinedWalls = rc.Geometry.Brep.JoinBreps(brepList, tolerance)[0]
                        cappedZone = joinedWalls.CapPlanarHoles(tolerance)
                        perimZones.append(cappedZone)
                    floorZones.extend(perimZones)
                    
                    
                    #Test to see if all of the generated zones are null and, if so, return the full floor mass.
                    noneTest = []
                    for zone in floorZones:
                        if zone == None:
                            noneTest.append(1)
                            warning = "The script has failed to create one of the zones because of a tolerance issue.  Try changing your Rhino Model's tolerance (prorbably try increasing) and recompute the GH definition to generate zones correctly."
                            print warning
                            ghenv.Component.AddRuntimeMessage(gh.GH_RuntimeMessageLevel.Warning, warning)
                        else: pass
                    
                    #Append the group to the full zone list.
                    if sum(noneTest) == len(floorZones):
                        genFailure = True
                        finalZones.append(mass[curveCount])
                        warning = "Failed to generate the perimieter zones for one floor as the geometry broke the script.  The problematic floor will be returned as a single zone."
                        print warning
                        ghenv.Component.AddRuntimeMessage(gh.GH_RuntimeMessageLevel.Warning, warning)
                    elif listCount == 0:
                        finalZones.append(floorZones)
                    else:
                        finalZones[curveCount].extend(floorZones)
                else:
                    finalZones.append(mass[curveCount])
                    print "One floor did not generate perimeter and core zones because the offsetting of the boundary causes part of the core to dissappear.  The floor will be returned as a single zone.  If perimeter zones are desired, try decreasing the perimeter depth."
            except:
                if len(floorCrvList) > 1 and listCount > 0: pass
                else:
                    try:
                        finalZones.append(mass[curveCount])
                        warning = "Failed to generate the perimieter zones for one floor as the floor's geometry is not accomodated by the script.  The floor will be returned as a single zone."
                        print warning
                        ghenv.Component.AddRuntimeMessage(gh.GH_RuntimeMessageLevel.Warning, warning)
                    except: pass
    
    # If the building is a courtyard building, generate the core zones and append them to the final zones.
    if len(coreZoneWallList) != 0 and genFailure == False:
        for floorCount, floor in enumerate(coreZoneWallList):
            coreZoneSurfaces = floor
            floorCurves = []
            ceilingCurves = []
            for brep in floor:
                edgeCurves = brep.DuplicateEdgeCurves(True)
                joinedEdgeCurves = rc.Geometry.Curve.JoinCurves(edgeCurves, tolerance, True)
                floorCurves.append(joinedEdgeCurves[0])
                ceilingCurves.append(joinedEdgeCurves[1])
            coreZoneSurfaces.append(rc.Geometry.Brep.CreatePlanarBreps(floorCurves)[0])
            coreZoneSurfaces.append(rc.Geometry.Brep.CreatePlanarBreps(ceilingCurves)[0])
            coreZone = rc.Geometry.Brep.JoinBreps(coreZoneSurfaces, tolerance)[0]
            finalZones[floorCount].append(coreZone)
    else: pass
    
    #If the top floor has not been included in the analysis above, append on the top floor mass.
    if topInc[0] == False:
        finalZones.append([mass[-1]])
    else: pass
    
    return finalZones    
def main(_bldgMasses, perimeterZoneDepth_, tmp_data):  
    #If the user had specified a perimeter zone depth, offset the floor curves to get perimeter and core.
    #Input: mass, perimDepth, floorCrvs[count], topInc[count], nurbsList[count]
    #Output: Nested list of splitZones for each level
    splitZones = []
    floorCrvs, topInc, nurbsList = tmp_data[0],tmp_data[1],tmp_data[2]
    if perimeterZoneDepth_ != []:
        #temporary comment until you can implement tree2nestedlst
        #for count, mass in enumerate(_bldgMasses):
        splitZones.append(splitPerimZones(_bldgMasses, perimeterZoneDepth_, floorCrvs[0], topInc[0], nurbsList[0]))
    return splitZones    

checkData = False
if _runIt == True:
    checkData = checkTheInputs()
if checkData == True:
    splitBldgMassesLists = main(_bldgMasses, perimeterZoneDepth_, tmp_data)
    if splitBldgMassesLists!= -1:
        splitBldgMasses = DataTree[Object]()
    
    names = DataTree[Object]()
    for i, buildingMasses in enumerate(splitBldgMassesLists):
        for j, mass in enumerate(buildingMasses):
            p = GH_Path(i,j)
            
            # in case mass is not a list change it to list
            try: mass[0]
            except: mass = [mass]
            
            newMass = []
            for brep in mass:
                if brep != None:
                    #Bake the objects into the Rhino scene to ensure that surface normals are facing the correct direction
                    sc.doc = rc.RhinoDoc.ActiveDoc #change target document
                    rs.EnableRedraw(False)
                    guid1 = [sc.doc.Objects.AddBrep(brep)]
                    if guid1:
                        a = [rs.coercegeometry(a) for a in guid1]
                        for g in a: g.EnsurePrivateCopy() #must ensure copy if we delete from doc
                        
                        rs.DeleteObjects(guid1)
                    
                    sc.doc = ghdoc #put back document
                    rs.EnableRedraw()
                    newMass.append(g)
                mass = newMass
            
            try:
                splitBldgMasses.AddRange(mass, p)
                #zoneNames = [str(i) + "_" + str(m) for m in range(len(mass))]
                #names.AddRange(zoneNames, p)
            except:
                splitBldgMasses.Add(mass, p)
                #names.Add(str(i) + "_" + str(j), p)
            