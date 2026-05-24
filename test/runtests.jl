using Test

@testset "BESSDispatch package" begin
    @testset "can be imported" begin
        using BESSDispatch

        @test BESSDispatch isa Module
    end
end
